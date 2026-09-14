"""Replay for the owner's run 2026-09-15 (batch 2): answers after Zoya asks a question.

V1: "uh for the budget" … 1 s pause … "five thousand rupees a night" was cut at the first pause and
    sent alone. Pass: ONE dispatch holding both parts.
V2: "Zoya 5000" in the follow-up window was taken for a repeated wake. Pass: "5000" is dispatched.
V3: Zoya's own words starting while she speaks ("I need a clear answer.") were dispatched.
    Pass: nothing is dispatched.
Real models (base.en, turbo, Smart Turn) on synthetic `say` audio, fed block by block in real
time; nothing plays on the speakers. Needs the GPU models, so it is an eval, not a pytest.
Usage: .venv/bin/python -u -m tests.evals.answer_turn_replay
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

from tests.evals.wake_junk_replay import RATE, fresh, synthesize  # noqa: E402
from zoya import audio, orchestrator, speech, voice  # noqa: E402


def feed(loop: voice.VoiceLoop, stream: np.ndarray, talking_until: float = 0.0) -> None:
    blocks = stream[: len(stream) // voice.VAD_BLOCK * voice.VAD_BLOCK].reshape(-1, voice.VAD_BLOCK)
    started = time.monotonic()
    for index, block in enumerate(blocks):
        due = started + (index + 1) * voice.BLOCK_S
        if (lag := due - time.monotonic()) > 0:
            time.sleep(lag)
        speech.is_speaking = lambda at=due: at - started < talking_until  # noqa: E731
        loop._on_block(due, block)


def answer_window(loop: voice.VoiceLoop) -> None:
    fresh(loop)
    loop.held = None
    loop.answer_expected = True
    loop._open_follow_up()


def main() -> int:
    engine = SimpleNamespace(one_shot_at=0.0, silence_all=lambda: None)
    audio.engine = lambda: engine
    audio.duck = audio.restore = audio.earcon = lambda *_a: None
    speech.narrate = lambda *_a, **_k: None
    dispatched: list[str] = []
    orchestrator.start_task = lambda text, *_a, **_k: dispatched.append(text) or SimpleNamespace(
        shared=False
    )
    loop = voice.VoiceLoop()
    rng = np.random.default_rng(1)
    silence = lambda s: (rng.standard_normal(int(s * RATE)) * 0.002).astype("f4")  # noqa: E731
    with tempfile.TemporaryDirectory() as folder:
        part1 = synthesize("uh, for the budget", Path(folder))
        part2 = synthesize("five thousand rupees a night", Path(folder))
        number = synthesize("Zoya, 5000", Path(folder))
        echo = synthesize("I need a clear answer.", Path(folder))
    results = {}
    feed(loop, silence(4.0))  # background history
    answer_window(loop)
    feed(loop, np.concatenate([part1, silence(1.0), part2, silence(3.5)]))
    results["V1 merged"] = (list(dispatched), len(dispatched) == 1 and "night" in dispatched[0])
    dispatched.clear()
    answer_window(loop)
    feed(loop, np.concatenate([number, silence(4.0)]))
    results["V2 number"] = (list(dispatched), len(dispatched) == 1 and "5000" in dispatched[0])
    dispatched.clear()
    answer_window(loop)
    feed(loop, np.concatenate([echo, silence(3.0)]), talking_until=len(echo) / RATE)
    results["V3 echo"] = (list(dispatched), dispatched == [])
    for name, (sent, ok) in results.items():
        print(f"{name}: {'PASS' if ok else 'FAIL'} dispatched={sent}")
    return 0 if all(ok for _, ok in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
