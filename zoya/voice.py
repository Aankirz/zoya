"""Hands-free voice loop (§9.1, STACK §2, D19, D48).

Mic → Silero VAD (always on) → Whisper base.en checks each finished utterance for "Hey Zoya"
and, while Zoya talks or works, the last 2 s every 150 ms for "Zoya, stop" (D51: base.en runs
on the Apple GPU via mlx, ~30 ms a call) → after wake, record until ~0.5 s silence →
mlx-whisper large-v3-turbo → router → task. Push-to-talk (Control + Option) records from
key-down. While Zoya talks, only the stop spotter listens (echo protection).

APIs (verified against the installed packages, 2026-09-14):
- https://github.com/SYSTRAN/faster-whisper — Silero VAD v6 ONNX ships in faster_whisper/assets;
  driven block by block with carried state as in https://github.com/snakers4/silero-vad
  (512 samples + 64 context at 16 kHz). WhisperModel.transcribe for the CPU spotter switch.
- https://github.com/ml-explore/mlx-examples/tree/main/whisper — mlx_whisper.transcribe(ndarray,
  path_or_hf_repo, initial_prompt, language, temperature, condition_on_previous_text).
- Quartz CGEventSourceFlagsState — modifier keys, no event tap or Input Monitoring needed.
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from zoya import audio, orchestrator, speech
from zoya.config import (
    AFTER_WAKE_WAIT_S,
    COMMAND_END_SILENCE_S,
    ECHO_TAIL_S,
    LOG_DIR,
    MAX_UTTERANCE_S,
    MIC_READ_TIMEOUT_S,
    MIC_SAMPLE_RATE_HZ,
    PARTIAL_EVERY_S,
    PARTIAL_MIN_S,
    PRE_ROLL_S,
    SPOTTER_ENGINE,
    STT_MODEL_REPO,
    TIMING_LOG,
    VAD_BLOCK,
    VAD_THRESHOLD,
    WAKE_END_SILENCE_S,
    WAKE_MODEL,
    WAKE_WINDOW_S,
)
from zoya.router import STOP, clean_command

log = logging.getLogger(__name__)

MS_PER_S = 1000
BLOCK_S = VAD_BLOCK / MIC_SAMPLE_RATE_HZ
VAD_CONTEXT = 64
VAD_STATE_SHAPE = (1, 1, 128)
STOP_WINDOW_S = 2.0  # spot "stop" in the last 2 s of mic audio, across utterance boundaries
WARM_UP_S = 1.0
FIRST_WORD_WAIT_S = 5.0
FIRST_WORD_POLL_S = 0.02
NAME_MEMORY_S = 2.5  # "Zoya … stop" may land in two different 2 s windows

# --- Parsers (tested: tests/test_voice_spotter.py) ------------------------------------

# Lenient "Zoya" (§7.1): zoya, zoia, zooeya, zoa, zoyah — not soya, sonia, zoe.
NAME = re.compile(r"^z(?:oo?e?y|oi|o)ah?$")
# Whisper sometimes merges the greeting: "Hizoya", "Hezoya".
MERGED_WAKE = re.compile(r"^(?:hey|hi|he|hay|ok|okay)z(?:oo?e?y|oi|o)ah?$")
WORD = re.compile(r"[a-z]+")
WAKE_NAME_WORDS = 3
# Only greetings may come before the name: "I bought soya milk" transcribes as "I bought
# Zoya milk" even on the whole clip (Phase 2 test), so "name anywhere in 3 words" isn't enough.
GREETINGS = {"hey", "hi", "hay", "he", "hello", "ok", "okay", "oh", "a"}
STOP_WORDS = {"stop", "cancel", "quiet", "ruko", "ruk", "bas", "chup"}
MAX_STOP_PHRASE_WORDS = 6
STATUS = re.compile(r"\bwhat(?:'s| is| are you)\s+(?:running|doing|working on)\b", re.I)


def words(text: str) -> list[str]:
    return WORD.findall(text.lower())


def is_wake(text: str) -> bool:
    """A Zoya-like name within the first 3 words, with only greetings before it (D19, D51)."""
    spoken = words(text)[:WAKE_NAME_WORDS]
    for index, word in enumerate(spoken):
        if NAME.match(word) or MERGED_WAKE.match(word):
            return all(earlier in GREETINGS for earlier in spoken[:index])
    return False


def is_stop(text: str) -> bool:
    """ "Zoya, stop" / "stop Zoya" / "Zoya ruko": the name AND a stop word in a short phrase.

    Requiring the name keeps Zoya's own speech ("Okay, stopped.") from stopping her.
    """
    spoken = words(text)
    if not spoken or len(spoken) > MAX_STOP_PHRASE_WORDS:
        return False
    return any(NAME.match(w) for w in spoken) and any(w in STOP_WORDS for w in spoken)


def is_stop_command(text: str) -> bool:
    """A captured command that means stop ("Hey Zoya … stop", router STOP phrases)."""
    return is_stop(text) or bool(STOP.match(clean_command(text)))


# --- Models -----------------------------------------------------------------------------


class StreamingVad:
    """Silero VAD v6 (bundled with faster-whisper) with state carried across 32 ms blocks."""

    def __init__(self) -> None:
        from faster_whisper.vad import get_vad_model

        self._session = get_vad_model().session
        self._h = np.zeros(VAD_STATE_SHAPE, dtype=np.float32)
        self._c = np.zeros(VAD_STATE_SHAPE, dtype=np.float32)
        self._context = np.zeros(VAD_CONTEXT, dtype=np.float32)

    def __call__(self, block: np.ndarray) -> float:
        batch = np.concatenate([self._context, block])[None, :]
        out, self._h, self._c = self._session.run(
            None, {"input": batch, "h": self._h, "c": self._c}
        )
        self._context = block[-VAD_CONTEXT:]
        return float(np.asarray(out).reshape(-1)[0])


def load_whisper(repo: str, **options: str) -> Callable[[np.ndarray], str]:
    """An mlx-whisper transcriber, loaded and warmed now (the first call is slow, D48)."""
    import mlx.core as mx
    import mlx_whisper
    from mlx_whisper.load_models import load_model
    from mlx_whisper.transcribe import ModelHolder

    model = load_model(repo, dtype=mx.float16)  # transcribe()'s default fp16 dtype

    def transcribe(samples: np.ndarray) -> str:
        # ponytail: mlx-whisper 0.4.3 caches ONE model, so alternating base.en and turbo reloaded
        # weights every call (+350 ms spot, turbo 0.6 → 1.3 s). Hand it ours; re-check on upgrade.
        ModelHolder.model, ModelHolder.model_path = model, repo
        result = mlx_whisper.transcribe(
            samples,
            path_or_hf_repo=repo,
            temperature=0.0,  # no temperature fallback re-runs: keeps each call bounded
            condition_on_previous_text=False,
            **options,
        )
        return str(result.get("text", "")).strip()

    transcribe(np.zeros(int(WARM_UP_S * MIC_SAMPLE_RATE_HZ), dtype=np.float32))
    return transcribe


def load_cpu_spotter() -> Callable[[np.ndarray], str]:
    """D19's original spotter: faster-whisper base.en int8 on CPU (~250 ms/call). Stage fallback."""
    from faster_whisper import WhisperModel

    model = WhisperModel("base.en", device="cpu", compute_type="int8")

    def transcribe(samples: np.ndarray) -> str:
        segments, _ = model.transcribe(
            samples, language="en", initial_prompt="Zoya", beam_size=1, vad_filter=False
        )
        return " ".join(segment.text for segment in segments).strip()

    transcribe(np.zeros(int(WARM_UP_S * MIC_SAMPLE_RATE_HZ), dtype=np.float32))
    return transcribe


def push_to_talk_held() -> bool:
    import Quartz

    flags = Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateHIDSystemState)
    wanted = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskAlternate
    return flags & wanted == wanted


# --- Listener ---------------------------------------------------------------------------


@dataclass
class Segment:
    blocks: list[np.ndarray]
    last_voice_at: float
    woke_at: float | None = None  # set once "Zoya" was heard in this segment

    @property
    def seconds(self) -> float:
        return len(self.blocks) * BLOCK_S

    def samples(self, head_s: float = MAX_UTTERANCE_S) -> np.ndarray:
        return np.concatenate(self.blocks[: max(1, int(head_s / BLOCK_S))])


class VoiceLoop:
    def __init__(self, wake_enabled: bool = True, test_wake: bool = False) -> None:
        self.wake_enabled = wake_enabled
        self.test_wake = test_wake
        self.vad = StreamingVad()
        self.spot = (
            load_cpu_spotter()
            if SPOTTER_ENGINE == "faster-whisper"
            else load_whisper(WAKE_MODEL, language="en", initial_prompt="Zoya")
        )
        self.stt = load_whisper(STT_MODEL_REPO)  # multilingual: Hinglish → Devanagari (D42)
        self.mic: queue.Queue[tuple[float, np.ndarray]] = queue.Queue()
        self.pre_roll: deque[np.ndarray] = deque(maxlen=int(PRE_ROLL_S / BLOCK_S))
        self.recent: deque[np.ndarray] = deque(maxlen=int(STOP_WINDOW_S / BLOCK_S))
        self.last_voice_at = 0.0
        self.last_stop_check = 0.0
        self.name_heard_at = 0.0
        self.segment: Segment | None = None
        self.awaiting_command_until = 0.0  # "Hey Zoya" … pause … command
        self.ptt: Segment | None = None
        self.task: threading.Thread | None = None
        self.last_spoke_at = 0.0

    # --- main loop ---------------------------------------------------------------------

    def run(self, stop_event: threading.Event) -> None:
        import sounddevice as sd

        def on_audio(indata: np.ndarray, _frames, _time, _status) -> None:  # noqa: ANN001
            self.mic.put((time.monotonic(), indata[:, 0].copy()))

        with sd.InputStream(
            samplerate=MIC_SAMPLE_RATE_HZ,
            channels=1,
            dtype="float32",
            blocksize=VAD_BLOCK,
            callback=on_audio,
        ):
            while not stop_event.is_set():
                try:
                    arrival, block = self.mic.get(timeout=MIC_READ_TIMEOUT_S)
                except queue.Empty:
                    continue
                self._on_block(arrival, block)

    def _on_block(self, arrival: float, block: np.ndarray) -> None:
        voiced = self.vad(block) >= VAD_THRESHOLD
        self.recent.append(block)
        if voiced:
            self.last_voice_at = arrival
        if speech.is_speaking():
            self.last_spoke_at = time.monotonic()
        self._check_stop(arrival)
        if self._push_to_talk(arrival, block):
            return
        if self.segment is None:
            self.pre_roll.append(block)
            if voiced:
                self.segment = Segment([*self.pre_roll, block], arrival)
                if time.monotonic() < self.awaiting_command_until:
                    self.segment.woke_at = time.monotonic()  # already awake: this is the command
            return
        self.segment.blocks.append(block)
        if voiced:
            self.segment.last_voice_at = arrival
        if self._segment_ended(self.segment, arrival):
            ended, self.segment = self.segment, None
            self.pre_roll.clear()
            self._on_segment_end(ended)

    def _segment_ended(self, segment: Segment, arrival: float) -> bool:
        silence = COMMAND_END_SILENCE_S if segment.woke_at is not None else WAKE_END_SILENCE_S
        return arrival - segment.last_voice_at >= silence or segment.seconds >= MAX_UTTERANCE_S

    # --- spotting: "stop" always, the wake word only when Zoya is quiet ----------------------

    def _zoya_busy(self) -> bool:
        recently_spoke = time.monotonic() - self.last_spoke_at < ECHO_TAIL_S
        return speech.is_speaking() or recently_spoke or self._task_running()

    def _check_stop(self, arrival: float) -> None:
        """While Zoya talks or works, re-read the last 2 s every 150 ms (false stops fail safe)."""
        now = time.monotonic()
        if not self._zoya_busy() or now - self.last_stop_check < PARTIAL_EVERY_S:
            return
        if (
            arrival - self.last_voice_at > STOP_WINDOW_S
            or len(self.recent) * BLOCK_S < PARTIAL_MIN_S
        ):
            return
        self.last_stop_check = now
        text = self._spot(np.concatenate(self.recent))
        if any(NAME.match(word) for word in words(text)):
            self.name_heard_at = now
        recent_name = now - self.name_heard_at < NAME_MEMORY_S
        if is_stop(text) or (recent_name and is_stop(f"Zoya {text}")):
            self._stop(self.last_voice_at, text, partial=True)

    def _spot(self, samples: np.ndarray) -> str:
        started = time.monotonic()
        text = self.spot(samples)
        log.debug("spot %d ms: %r", (time.monotonic() - started) * MS_PER_S, text)
        return text

    def _on_segment_end(self, segment: Segment) -> None:
        if segment.woke_at is not None:
            self._command(segment)
            return
        if self._zoya_busy() or not self.wake_enabled:
            return  # echo protection: only the stop spotter listens now
        # Whole utterance only: partial audio makes Whisper hallucinate the "Zoya" prompt.
        text = self._spot(segment.samples(WAKE_WINDOW_S))
        if is_stop(text):
            self._stop(segment.last_voice_at, text, partial=False)
        elif is_wake(text):
            self._wake(segment, text)
            if clean_command(text):
                self._command(segment)  # "Hey Zoya, open Spotify" in one breath
            else:
                self._await_command()  # "Hey Zoya" … pause … command
        elif self.test_wake and text:
            print(f"  no wake: {text!r}")

    def _await_command(self) -> None:
        self.awaiting_command_until = time.monotonic() + AFTER_WAKE_WAIT_S

    def _wake(self, segment: Segment, text: str) -> None:
        segment.woke_at = time.monotonic()
        audio.earcon("listening")
        after_end = round((segment.woke_at - segment.last_voice_at) * MS_PER_S)
        print(f"WAKE {after_end} ms after the phrase ended — heard {text!r}")
        _log_voice({"event": "wake", "phrase_end_to_earcon_ms": after_end, "heard": text})

    def _stop(self, voice_end_at: float, text: str, partial: bool) -> None:
        stopped_at = time.monotonic()
        was_busy = self._zoya_busy()
        orchestrator.stop_task()
        audio.engine().silence_all()
        audio.earcon("stop")
        after_end = round((stopped_at - voice_end_at) * MS_PER_S)
        self.segment = None
        self.recent.clear()  # don't hear the same "stop" twice
        self.name_heard_at = 0.0
        self.awaiting_command_until = 0.0
        print(f"STOP {after_end} ms after last voice (partial={partial}) — heard {text!r}")
        _log_voice(
            {
                "event": "stop",
                "partial": partial,
                "busy": was_busy,
                "last_voice_to_silence_ms": after_end,
            }
        )

    # --- push-to-talk ----------------------------------------------------------------------

    def _push_to_talk(self, arrival: float, block: np.ndarray) -> bool:
        held = push_to_talk_held()
        if self.ptt is None and not held:
            return False
        if self.ptt is None:
            self.ptt = Segment([*self.pre_roll, block], arrival, woke_at=time.monotonic())
            self.segment = None
            audio.earcon("listening")
            print("PUSH-TO-TALK down")
            return True
        self.ptt.blocks.append(block)
        if held and self.ptt.seconds < MAX_UTTERANCE_S:
            return True
        ended, self.ptt = self.ptt, None
        ended.last_voice_at = arrival
        print("PUSH-TO-TALK up")
        self._command(ended)
        return True

    # --- commands ---------------------------------------------------------------------------

    def _task_running(self) -> bool:
        return self.task is not None and self.task.is_alive()

    def _command(self, segment: Segment) -> None:
        endpointed_at = time.monotonic()
        audio.earcon("heard")
        audio.earcon("working")
        speech.reset_timing()
        started = time.monotonic()
        text = self.stt(segment.samples())
        stt_ms = round((time.monotonic() - started) * MS_PER_S)
        endpoint_ms = round((endpointed_at - segment.last_voice_at) * MS_PER_S)
        print(f"HEARD {text!r} (endpoint {endpoint_ms} ms, stt {stt_ms} ms)")
        if self.test_wake:
            audio.earcon("success")
            return
        if not clean_command(text) and time.monotonic() >= self.awaiting_command_until:
            self._await_command()  # push-to-talk or wake with nothing after it yet
            audio.engine().silence_all()  # end the working loop
            return
        self.awaiting_command_until = 0.0
        self._dispatch(text, segment.last_voice_at, {"endpoint_ms": endpoint_ms, "stt_ms": stt_ms})

    def _dispatch(self, text: str, speech_end_at: float, pre: dict[str, int]) -> None:
        if not clean_command(text):
            audio.engine().silence_all()  # nothing heard: end the working loop quietly
            return
        if is_stop_command(text):
            self._stop(speech_end_at, text, partial=False)
            return
        if STATUS.search(text):
            audio.earcon("success")
            speech.narrate(orchestrator.task_status())
            return
        if self._task_running():
            audio.earcon("error")
            speech.narrate("I'm still on the last task. Say Zoya, stop, to cancel it.")
            return
        self.task = orchestrator.start_task(
            text, pre, on_done=lambda result: _report(result, speech_end_at, pre)
        )


def _report(result: orchestrator.CommandResult, speech_end_at: float, pre: dict[str, int]) -> None:
    done_ms = round((time.monotonic() - speech_end_at) * MS_PER_S)
    deadline = time.monotonic() + FIRST_WORD_WAIT_S  # fast replies are spoken after "done"
    while speech.first_audio_at is None and time.monotonic() < deadline:
        time.sleep(FIRST_WORD_POLL_S)
    first = speech.first_audio_at
    first_word_ms = round((first - speech_end_at) * MS_PER_S) if first else None
    print(
        f"DONE route={result.decision.route} tool={result.decision.tool} ok={result.ok} "
        f"speech_end→done {done_ms} ms, first word {first_word_ms} ms, stages {result.timings_ms}"
    )
    print(f"  zoya: {result.spoken}")
    _log_voice(
        {
            "event": "command",
            "task_id": result.task_id,
            "route": result.decision.route,
            "ok": result.ok,
            "speech_end_to_done_ms": done_ms,
            "speech_end_to_first_word_ms": first_word_ms,
            **pre,
        }
    )


def _log_voice(record: dict) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    line = {"at": datetime.now(UTC).isoformat(timespec="milliseconds"), "voice": True, **record}
    with TIMING_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")
