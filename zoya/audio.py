"""Audio engine (§9.10): one output stream mixing speech, earcons and the working loop.

Earcons are preloaded WAVs (built by scripts/build_sounds.sh, §7.3). One mixer callback
means stop is instant — clearing a buffer silences the next 10 ms block — and nothing
spawns a process per sound. The working loop is ducked −18 dB under speech.

APIs: https://python-sounddevice.readthedocs.io/en/0.5.6/api/streams.html#sounddevice.OutputStream
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from collections import deque
from collections.abc import Callable
from functools import cache

import numpy as np

from zoya import events
from zoya.config import (
    AUDIO_BLOCK_SIZE,
    AUDIO_SAMPLE_RATE_HZ,
    DUCK_FRACTION,
    DUCK_STATE_FILE,
    LOOP_DUCK_GAIN,
    OSASCRIPT_TIMEOUT_S,
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


# --- Ducking other apps while Zoya listens (Wispr Flow "Mute Music While Dictating") ------------
# ponytail: macOS has no per-app volume API, so the whole output drops while listening and comes
# back before Zoya answers. One worker keeps duck/restore in order; osascript needs no permission.

_ducked_from: int | None = None
_volume_jobs: queue.Queue[Callable[[], None]] = queue.Queue()


def _volume_worker() -> None:
    while True:
        job = _volume_jobs.get()
        try:
            job()
        except Exception as error:  # noqa: BLE001 — a failed duck must never break listening
            log.warning("volume change failed (%s)", type(error).__name__)


def _volume(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=OSASCRIPT_TIMEOUT_S,
        check=True,
    )
    return result.stdout.strip()


def _saved_level() -> int | None:
    """The pre-duck volume a run wrote to DUCK_STATE_FILE (still there if it was killed)."""
    try:
        return int(json.loads(DUCK_STATE_FILE.read_text())["volume"])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as error:
        log.warning("unreadable duck state (%s) — ignored", type(error).__name__)
        return None


def _save_level(level: int) -> None:
    DUCK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    partial = DUCK_STATE_FILE.with_suffix(".tmp")
    partial.write_text(json.dumps({"volume": level}))
    os.replace(partial, DUCK_STATE_FILE)  # atomic: a kill mid-write never leaves half a file


def _duck_now() -> None:
    global _ducked_from
    if _ducked_from is not None:
        return
    # A killed run's saved level is the real one: reading the ducked volume as "normal"
    # compounded 100 → 30 → 9 → 3 → 0 over repeated kills.
    saved = _saved_level()
    level = saved if saved is not None else int(_volume("output volume of (get volume settings)"))
    _save_level(level)  # before lowering, so even kill -9 mid-duck can be undone at next start
    _ducked_from = level  # set before lowering, so a failed or partial duck is still restored
    _volume(f"set volume output volume {round(level * DUCK_FRACTION)}")


def _restore_now() -> None:
    """Put back the user's exact volume; stay marked ducked until that really succeeded."""
    global _ducked_from
    if _ducked_from is None:
        return
    try:
        _volume(f"set volume output volume {_ducked_from}")
    except (subprocess.SubprocessError, OSError):
        _volume(f"set volume output volume {_ducked_from}")  # one retry, then the worker logs it
    _ducked_from = None
    DUCK_STATE_FILE.unlink(missing_ok=True)


def restore_after_kill() -> None:
    """At startup: a run killed while ducked (kill -9, closed terminal) left the Mac quiet."""
    saved = _saved_level()
    if saved is None:
        return
    _volume(f"set volume output volume {saved}")
    DUCK_STATE_FILE.unlink(missing_ok=True)
    log.warning("restored the volume to %d left ducked by a killed run", saved)


@cache
def _start_volume_worker() -> None:
    threading.Thread(target=_volume_worker, name="zoya-duck", daemon=True).start()


def duck() -> None:
    _start_volume_worker()
    _volume_jobs.put(_duck_now)


def restore() -> None:
    _start_volume_worker()
    _volume_jobs.put(_restore_now)


def restore_blocking(timeout_s: float = OSASCRIPT_TIMEOUT_S) -> None:
    """On exit: never leave the Mac quiet."""
    done = threading.Event()
    restore()
    _volume_jobs.put(done.set)
    done.wait(timeout_s)


def is_ducked() -> bool:
    return _ducked_from is not None


@cache
def engine() -> Engine:
    """Start the engine once and route EarconEvents to it."""
    started = Engine()
    events.subscribe(events.EARCON, lambda event: started.earcon(event.kind))
    return started


def earcon(kind: events.EarconKind) -> None:
    events.emit(events.EarconEvent(kind))
