"""Replay for the owner's run 2026-09-15: `HEARD ''` right after a wake.

The wake chime (wake.wav) plays the moment "Hey Zoya" is recognised, the mic hears it, Silero calls
4 of its 28 blocks speech, and inside the wait window that blip became a "command": heard +
working earcons, ~600 ms of turbo on the loop thread, an empty transcript.

Here the loop's own earcons are fed back into the mic from the moment it plays them (a fake
engine, so nothing sounds on the speakers). Pass: the command is dispatched, turbo never runs on
the chime, and no "heard" earcon plays before the real command. Needs the GPU models and macOS
`say` + ffmpeg, so it is an eval, not a pytest.
Usage: .venv/bin/python -u -m tests.evals.echo_chime_replay
"""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"  # pinned models from the cache only (AUDIT §6)

import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402

from tests.evals.wake_junk_replay import RATE, chime, fresh, synthesize  # noqa: E402
from zoya import audio, events, orchestrator, speech, voice  # noqa: E402

MIC_GAIN = 1.0  # chime at the mic as loud as the synthetic user (worst case)


class FakeEngine:
    """Records earcons and when they sound; the replay mixes the chime into later mic blocks."""

    def __init__(self) -> None:
        self.one_shot_at = 0.0
        self.sounding: list[tuple[float, np.ndarray]] = []
        self.kinds: list[tuple[float, str]] = []

    def on_earcon(self, event: events.EarconEvent) -> None:
        now = time.monotonic()
        self.kinds.append((now, event.kind))
        if event.kind == "listening":
            samples = chime() * 2 * MIC_GAIN  # chime() halves it
            self.sounding.append((now, samples))
            self.one_shot_at = now + len(samples) / RATE

    def mic(self, due: float, block: np.ndarray) -> np.ndarray:
        out = block.copy()
        for started, samples in self.sounding:
            offset = int((due - started) * RATE) - len(block)
            if 0 <= offset < len(samples):
                piece = samples[offset : offset + len(block)]
                out[: len(piece)] += piece
        return out

    def silence_all(self) -> None:
        pass


def main() -> int:
    engine = FakeEngine()
    audio.engine = lambda: engine
    audio.duck = audio.restore = lambda: None
    speech.is_speaking = lambda: False
    events.subscribe(events.EARCON, engine.on_earcon)
    dispatched: list[tuple[float, str]] = []
    speech.narrate = lambda *_a, **_k: None  # never speak from an eval

    def start_task(text: str, *_args: object, **_kwargs: object) -> SimpleNamespace:
        dispatched.append((time.monotonic(), text))
        return SimpleNamespace(shared=False)

    orchestrator.start_task = start_task

    loop = voice.VoiceLoop()
    stt, transcripts = loop.stt, []
    loop.stt = lambda samples: transcripts.append(stt(samples)) or transcripts[-1]
    rng = np.random.default_rng(1)
    silence = lambda s: (rng.standard_normal(int(s * RATE)) * 0.002).astype("f4")  # noqa: E731
    with tempfile.TemporaryDirectory() as folder:
        wake = synthesize("Hey Zoya", Path(folder))
        command = synthesize("What's the capital of Japan?", Path(folder))
    fresh(loop)
    stream = np.concatenate([silence(4.0), wake, silence(2.5), command, silence(2.0)])
    blocks = stream[: len(stream) // voice.VAD_BLOCK * voice.VAD_BLOCK].reshape(-1, voice.VAD_BLOCK)
    started = time.monotonic()
    for index, block in enumerate(blocks):
        due = started + (index + 1) * voice.BLOCK_S
        if (lag := due - time.monotonic()) > 0:
            time.sleep(lag)
        loop._on_block(due, engine.mic(due, block))

    command_at = dispatched[0][0] if dispatched else float("inf")
    early_heard = [k for at, k in engine.kinds if k == "heard" and at < command_at - 1.5]
    # Turbo runs twice when right: the wake veto check on "Hey Zoya", then the command.
    ok = dispatched and "japan" in dispatched[0][1].lower() and len(transcripts) == 2
    ok = ok and not early_heard
    print(f"dispatched {[t for _, t in dispatched]}")
    print(f"turbo calls {len(transcripts)}: {transcripts!r}")
    print(f"earcons {[k for _, k in engine.kinds]}; 'heard' before the command: {len(early_heard)}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
