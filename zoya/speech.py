"""narrate(): Zoya speaks (D33, D41, STACK §2), with barge-in (Phase 2).

Order: Amazon Polly Kajal (neural, en-IN, ap-south-1) → ElevenLabs Tara →
macOS `say`, so Zoya is never silent. Speech runs on one background worker so
the fast path's timing never includes audio playback, and sentences never overlap.
Audio streams chunk by chunk into zoya/audio.py as it arrives; cancel() drops
everything queued or playing within one 10 ms mixer block.

APIs (verified 2026-09-14):
- https://docs.aws.amazon.com/polly/latest/dg/API_SynthesizeSpeech.html (pcm = 16-bit mono LE)
- https://elevenlabs.io/docs/api-reference/text-to-speech/convert (output_format pcm_16000)
"""

from __future__ import annotations

import itertools
import logging
import os
import queue
import subprocess
import threading
import time
from collections.abc import Iterator

from zoya import audio, aws, events
from zoya.config import (
    DISABLE_TTS_ENV,
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_TIMEOUT_S,
    MACOS_FALLBACK_VOICE,
    POLLY_CHUNK_BYTES,
    POLLY_ENGINE,
    POLLY_LANGUAGE_CODE,
    POLLY_VOICE_ID,
    SAY_TIMEOUT_S,
    SPEECH_DRAIN_MARGIN_S,
    SPEECH_SAMPLE_RATE_HZ,
)

BYTES_PER_SAMPLE = 2
DRAIN_POLL_S = 0.02

log = logging.getLogger(__name__)

_queue: queue.Queue[str] = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()
_generation = 0  # bumped by cancel(); a sentence from an older generation stops
_busy = threading.Event()
_say_process: subprocess.Popen | None = None
first_audio_at: float | None = None  # monotonic time of the first audio since reset_timing()


class Cancelled(Exception):
    """The sentence was cut off by cancel()."""


def _disabled(engine: str) -> bool:
    return engine in os.environ.get(DISABLE_TTS_ENV, "").split(",")


def _polly_chunks(text: str) -> Iterator[bytes]:
    polly = aws.client("polly")
    if polly is None:
        raise RuntimeError("AWS disabled")
    response = polly.synthesize_speech(
        Text=text,
        VoiceId=POLLY_VOICE_ID,
        Engine=POLLY_ENGINE,
        LanguageCode=POLLY_LANGUAGE_CODE,
        OutputFormat="pcm",
        SampleRate=str(SPEECH_SAMPLE_RATE_HZ),
    )
    yield from response["AudioStream"].iter_chunks(POLLY_CHUNK_BYTES)


def _elevenlabs_chunks(text: str) -> Iterator[bytes]:
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"], timeout=ELEVENLABS_TIMEOUT_S)
    yield from client.text_to_speech.convert(
        voice_id=os.environ["ELEVENLABS_VOICE_ID"],
        text=text,
        model_id=ELEVENLABS_MODEL_ID,
        output_format=f"pcm_{SPEECH_SAMPLE_RATE_HZ}",
    )


def _check(generation: int) -> None:
    if generation != _generation:
        raise Cancelled


def _stream(chunks: Iterator[bytes], generation: int) -> float:
    """Feed audio to the mixer as it arrives. Returns seconds of audio queued."""
    global first_audio_at
    engine = audio.engine()
    carry = b""
    total_bytes = 0
    for chunk in chunks:
        _check(generation)
        data = carry + chunk
        carry = data[len(data) // BYTES_PER_SAMPLE * BYTES_PER_SAMPLE :]
        whole = data[: len(data) - len(carry)]
        if whole:
            if first_audio_at is None:
                first_audio_at = time.monotonic()
            engine.add_speech(whole)
            total_bytes += len(whole)
    return total_bytes / BYTES_PER_SAMPLE / SPEECH_SAMPLE_RATE_HZ


def _wait_played(seconds: float, generation: int) -> None:
    deadline = time.monotonic() + seconds + SPEECH_DRAIN_MARGIN_S
    engine = audio.engine()
    while engine.speech_pending() and time.monotonic() < deadline:
        _check(generation)
        time.sleep(DRAIN_POLL_S)


def _say(text: str, generation: int) -> None:
    global _say_process, first_audio_at
    if first_audio_at is None:
        first_audio_at = time.monotonic()
    _say_process = subprocess.Popen(
        ["say", "-v", MACOS_FALLBACK_VOICE, text], stdin=subprocess.DEVNULL
    )
    try:
        _say_process.wait(timeout=SAY_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        _say_process.kill()
    _say_process = None
    _check(generation)


def speak_now(text: str, generation: int | None = None) -> str:
    """Speak `text` and block until played or cancelled. Returns the engine that spoke."""
    generation = _generation if generation is None else generation
    for engine, synthesize in (("polly", _polly_chunks), ("elevenlabs", _elevenlabs_chunks)):
        if _disabled(engine):
            continue
        started = time.monotonic()
        chunks = synthesize(text)
        try:
            first = next(chunks)  # errors before any audio fall through to the next voice
        except Exception as error:  # noqa: BLE001 — fall through to the next voice
            log.warning("%s TTS failed (%s) — trying next voice", engine, type(error).__name__)
            continue
        log.info("tts engine=%s first_chunk_ms=%d", engine, (time.monotonic() - started) * 1000)
        seconds = _stream(itertools.chain([first], chunks), generation)
        _wait_played(seconds, generation)
        return engine
    _say(text, generation)
    return "macos"


def _run_worker() -> None:
    while True:
        text = _queue.get()
        generation = _generation
        _busy.set()
        try:
            speak_now(text, generation)
        except Cancelled:
            pass
        except Exception:  # noqa: BLE001 — speech must never kill the worker
            log.exception("speech playback failed")
        finally:
            _busy.clear()
            _queue.task_done()
            if _queue.empty():  # stage overlay: back from "speaking" (Phase 7)
                events.emit(events.OverlayEvent("", "idle", {"speech": "done"}))


def narrate(text: str) -> None:
    """Queue `text` to be spoken and return immediately."""
    global _worker
    clean = text.strip()
    if not clean:
        return
    events.emit(events.NarrateEvent(text=clean))
    with _worker_lock:
        if _worker is None:
            _worker = threading.Thread(target=_run_worker, name="zoya-speech", daemon=True)
            _worker.start()
    _queue.put(clean)


def cancel() -> None:
    """Barge-in: drop queued sentences, cut the one playing, silence the mixer."""
    global _generation
    _generation += 1
    while True:
        try:
            _queue.get_nowait()
            _queue.task_done()
        except queue.Empty:
            break
    audio.engine().clear_speech()
    if (process := _say_process) is not None:
        process.kill()


def say_and_wait(text: str, timeout_s: float) -> bool:
    """Speak `text` after anything already queued; block until played. False if it was cancelled
    (stop / barge-in) or ran past `timeout_s` — the safety gate then treats it as not heard."""
    generation = _generation
    narrate(text)
    deadline = time.monotonic() + timeout_s
    # unfinished_tasks drops only after speak_now returned (played or cancelled), unlike empty().
    while (
        _queue.unfinished_tasks or audio.engine().speech_pending()
    ) and generation == _generation:
        if time.monotonic() > deadline:
            return False
        time.sleep(DRAIN_POLL_S)
    return generation == _generation


def is_speaking() -> bool:
    return _busy.is_set() or not _queue.empty() or audio.engine().speech_pending()


def reset_timing() -> None:
    global first_audio_at
    first_audio_at = None


def wait_until_quiet(timeout_s: float = SAY_TIMEOUT_S) -> None:
    """Block until everything queued has been spoken, at most `timeout_s` (used on exit)."""
    deadline = time.monotonic() + timeout_s
    while is_speaking() and time.monotonic() < deadline:
        time.sleep(DRAIN_POLL_S)
