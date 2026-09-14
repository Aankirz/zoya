"""Regression replay: junk audio after a wake must not swallow the command (Phase 2 live bug).

Owner's live run: "Hi Zoya!" → the wake chime (or Spotify) was captured as the command and
transcribed "you" / "감사합니다" → the wake was used up and the real command ignored. Root cause
confirmed with this replay: fails on 0f24774, passes after a8fcd83.

Feeds [synthetic "Hey Zoya"] → [junk: the wake chime or synthetic music] → [a command] through
the real VoiceLoop (VAD, spotter, turbo) with dispatch mocked. Needs the GPU models and macOS
`say` + ffmpeg, so it is an eval, not a pytest.
Usage: .venv/bin/python -u tests/evals/wake_junk_replay.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from zoya import audio, orchestrator, speech, voice
from zoya.config import MIC_SAMPLE_RATE_HZ, SOUNDS_DIR

SUBPROCESS_TIMEOUT_S = 30
RATE = MIC_SAMPLE_RATE_HZ


def synthesize(text: str, folder: Path) -> np.ndarray:
    aiff, wav = folder / "clip.aiff", folder / "clip.wav"
    subprocess.run(
        ["say", "-v", "Samantha", "-o", aiff, text], check=True, timeout=SUBPROCESS_TIMEOUT_S
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", aiff, "-ar", str(RATE), "-ac", "1", wav],
        check=True,
        timeout=SUBPROCESS_TIMEOUT_S,
    )
    return sf.read(wav, dtype="float32")[0]


def chime() -> np.ndarray:
    samples, rate = sf.read(SOUNDS_DIR / "wake.wav", dtype="float32")
    positions = np.arange(0, len(samples), rate / RATE)
    return (np.interp(positions, np.arange(len(samples)), samples) * 0.5).astype("f4")


def music(rng: np.random.Generator, seconds: float = 3.0) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    chord = sum(np.sin(2 * np.pi * f * t) for f in (220, 277, 330)) * 0.05
    kick = np.sin(2 * np.pi * 60 * t) * np.exp(-((t % 0.5) * 20)) * 0.3
    hat = rng.standard_normal(len(t)) * np.exp(-((t % 0.25) * 60)) * 0.05
    return (chord + kick + hat).astype("f4")


def replay(loop: voice.VoiceLoop, stream: np.ndarray) -> None:
    blocks = stream[: len(stream) // voice.VAD_BLOCK * voice.VAD_BLOCK].reshape(-1, voice.VAD_BLOCK)
    started = time.monotonic()
    for index, block in enumerate(blocks):
        due = started + (index + 1) * voice.BLOCK_S
        if (lag := due - time.monotonic()) > 0:
            time.sleep(lag)
        loop._on_block(due, block)


def main() -> int:
    audio.duck = audio.restore = lambda: None  # never touch the Mac's volume from an eval
    speech.is_speaking = lambda: False
    dispatched: list[str] = []
    orchestrator.start_task = lambda text, *_args, **_kwargs: dispatched.append(text)
    rng = np.random.default_rng(1)
    with tempfile.TemporaryDirectory() as folder:
        wake = synthesize("Hey Zoya", Path(folder))
        command = synthesize("What's the capital of Japan?", Path(folder))
    loop = voice.VoiceLoop()
    silence = lambda s: (rng.standard_normal(int(s * RATE)) * 0.002).astype("f4")  # noqa: E731
    failures = 0
    for name, junk in (("chime", chime()), ("music", music(rng))):
        dispatched.clear()
        replay(
            loop,
            np.concatenate(
                [silence(0.5), wake, silence(0.8), junk, silence(0.8), command, silence(1.5)]
            ),
        )
        passed = any("japan" in text.lower() for text in dispatched)
        failures += not passed
        print(f"junk={name}: dispatched={dispatched} → {'PASS' if passed else 'FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
