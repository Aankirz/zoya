"""Audio engine (§9.10): one output stream mixing speech, earcons and the working loop.

Earcons are preloaded WAVs (built by scripts/build_sounds.sh, §7.3). One mixer callback
means stop is instant — clearing a buffer silences the next 10 ms block — and nothing
spawns a process per sound. The working loop is ducked −18 dB under speech.

APIs: https://python-sounddevice.readthedocs.io/en/0.5.6/api/streams.html#sounddevice.OutputStream
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from functools import cache

import numpy as np

from zoya import events
from zoya.config import (
    AUDIO_BLOCK_SIZE,
    AUDIO_SAMPLE_RATE_HZ,
    LOOP_DUCK_GAIN,
    SOUNDS_DIR,
    SPEECH_SAMPLE_RATE_HZ,
)

log = logging.getLogger(__name__)

# EarconKind (events.py) → file in sounds/. "working" starts the loop; outcomes end it.
EARCON_FILES = {
    "listening": "wake",
    "heard": "release",
    "success": "success",
    "error": "error",
    "stop": "stop",
    "attention": "mention",
}
LOOP_FILE = "processing"
ENDS_LOOP = {"success", "error", "stop"}


def _load(name: str) -> np.ndarray:
    import soundfile as sf

    data, rate = sf.read(SOUNDS_DIR / f"{name}.wav", dtype="float32", always_2d=True)
    if rate != AUDIO_SAMPLE_RATE_HZ:
        raise RuntimeError(f"{name}.wav is {rate} Hz — rerun scripts/build_sounds.sh")
    return data[:, 0].copy()


def pcm16_to_output(pcm: bytes) -> np.ndarray:
    """16 kHz int16 speech → float32 at the mixer rate (linear interpolation)."""
    samples = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768
    ratio = AUDIO_SAMPLE_RATE_HZ / SPEECH_SAMPLE_RATE_HZ
    positions = np.arange(int(len(samples) * ratio)) / ratio
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


class Engine:
    def __init__(self) -> None:
        import sounddevice as sd

        self._earcons = {kind: _load(name) for kind, name in EARCON_FILES.items()}
        self._loop = _load(LOOP_FILE)
        self._lock = threading.Lock()
        self._speech: deque[np.ndarray] = deque()
        self._playing: list[list] = []  # [samples, position] one-shots
        self._loop_on = False
        self._loop_pos = 0
        self.last_earcon = ""
        self._stream = sd.OutputStream(
            samplerate=AUDIO_SAMPLE_RATE_HZ,
            channels=1,
            dtype="float32",
            blocksize=AUDIO_BLOCK_SIZE,
            callback=self._callback,
        )
        self._stream.start()

    # --- public API (thread-safe) ---------------------------------------------------

    def earcon(self, kind: str) -> None:
        with self._lock:
            if kind == "working":
                self._loop_on = True
                return
            if kind in ENDS_LOOP:
                self._loop_on = False
            if kind in self._earcons:
                self._playing.append([self._earcons[kind], 0])
                self.last_earcon = kind

    def add_speech(self, pcm: bytes) -> None:
        samples = pcm16_to_output(pcm)
        with self._lock:
            self._speech.append(samples)

    def speech_pending(self) -> bool:
        with self._lock:
            return bool(self._speech)

    def clear_speech(self) -> None:
        with self._lock:
            self._speech.clear()

    def silence_all(self) -> None:
        """Stop: drop speech, one-shots and the loop at the next block."""
        with self._lock:
            self._speech.clear()
            self._playing.clear()
            self._loop_on = False

    # --- mixer ------------------------------------------------------------------------

    def _callback(self, outdata: np.ndarray, frames: int, _time, _status) -> None:  # noqa: ANN001
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            speaking = self._fill_speech(out)
            self._mix_one_shots(out)
            if self._loop_on:
                self._mix_loop(out, LOOP_DUCK_GAIN if speaking else 1.0)
        np.clip(out, -1.0, 1.0, out=out)
        outdata[:, 0] = out

    def _fill_speech(self, out: np.ndarray) -> bool:
        filled = 0
        while filled < len(out) and self._speech:
            chunk = self._speech[0]
            take = min(len(chunk), len(out) - filled)
            out[filled : filled + take] += chunk[:take]
            filled += take
            if take == len(chunk):
                self._speech.popleft()
            else:
                self._speech[0] = chunk[take:]
        return filled > 0

    def _mix_one_shots(self, out: np.ndarray) -> None:
        for sound in self._playing:
            samples, position = sound
            piece = samples[position : position + len(out)]
            out[: len(piece)] += piece
            sound[1] = position + len(piece)
        self._playing = [s for s in self._playing if s[1] < len(s[0])]

    def _mix_loop(self, out: np.ndarray, gain: float) -> None:
        indices = (self._loop_pos + np.arange(len(out))) % len(self._loop)
        out += self._loop[indices] * gain
        self._loop_pos = int(indices[-1] + 1) % len(self._loop)


@cache
def engine() -> Engine:
    """Start the engine once and route EarconEvents to it."""
    started = Engine()
    events.subscribe(events.EARCON, lambda event: started.earcon(event.kind))
    return started


def earcon(kind: events.EarconKind) -> None:
    events.emit(events.EarconEvent(kind))
