"""narrate(): Zoya speaks (D33, D41, STACK §2). Phase 2 adds barge-in.

Order: Amazon Polly Kajal (neural, en-IN, ap-south-1) → ElevenLabs Tara →
macOS `say`, so Zoya is never silent. Speech runs on one background worker so
the fast path's timing never includes audio playback, and sentences never overlap.

APIs (verified 2026-09-14):
- https://docs.aws.amazon.com/polly/latest/dg/API_SynthesizeSpeech.html (pcm = 16-bit mono LE)
- https://elevenlabs.io/docs/api-reference/text-to-speech/convert (output_format pcm_16000)
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time

import numpy as np

from zoya import aws, events
from zoya.config import (
    ELEVENLABS_MODEL_ID,
    MACOS_FALLBACK_VOICE,
    POLLY_ENGINE,
    POLLY_LANGUAGE_CODE,
    POLLY_VOICE_ID,
    SPEECH_SAMPLE_RATE_HZ,
)

log = logging.getLogger(__name__)

_queue: queue.Queue[str] = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()


def _polly_pcm(text: str) -> bytes:
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
    return response["AudioStream"].read()


def _elevenlabs_pcm(text: str) -> bytes:
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    chunks = client.text_to_speech.convert(
        voice_id=os.environ["ELEVENLABS_VOICE_ID"],
        text=text,
        model_id=ELEVENLABS_MODEL_ID,
        output_format=f"pcm_{SPEECH_SAMPLE_RATE_HZ}",
    )
    return b"".join(chunks)


def _play_pcm(pcm: bytes) -> None:
    import sounddevice as sd

    sd.play(np.frombuffer(pcm, dtype=np.int16), SPEECH_SAMPLE_RATE_HZ)
    sd.wait()


def _say(text: str) -> None:
    subprocess.run(["say", "-v", MACOS_FALLBACK_VOICE, text], check=False)


def speak_now(text: str) -> str:
    """Speak `text` and block until done. Returns the engine that spoke."""
    for engine, synthesize in (("polly", _polly_pcm), ("elevenlabs", _elevenlabs_pcm)):
        started = time.monotonic()
        try:
            pcm = synthesize(text)
        except Exception as error:  # noqa: BLE001 — fall through to the next voice
            log.warning("%s TTS failed (%s) — trying next voice", engine, type(error).__name__)
            continue
        log.info("tts engine=%s synth_ms=%d", engine, (time.monotonic() - started) * 1000)
        _play_pcm(pcm)
        return engine
    _say(text)
    return "macos"


def _run_worker() -> None:
    while True:
        text = _queue.get()
        try:
            speak_now(text)
        except Exception:  # noqa: BLE001 — speech must never kill the worker
            log.exception("speech playback failed")
        finally:
            _queue.task_done()


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


def wait_until_quiet() -> None:
    """Block until everything queued has been spoken (used on exit)."""
    _queue.join()
