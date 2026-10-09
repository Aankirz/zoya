"""Audio mode of the S1-Listen simulator: the real VoiceLoop with the real VAD, spotter, turbo and
Smart Turn on the owner's recorded clips, fed on a virtual audio clock with speculation threads
running for real.

Measures what the owner feels: wake-phrase end → earcon (the loop's own `phrase_end_to_earcon_ms`,
earcon playback itself excluded), wakes and false wakes on the labelled wake clips, and "Zoya,
stop" catches (with a task running) on the stop clips. Nothing plays or records; nothing is
written to logs/. Needs the GPU models, so it is an eval, not a pytest.

Usage: .venv/bin/python -u -m tests.evals.listen_audio [before] [realtime]
"realtime" also waits for each block's arrival time, so the GPU idles between blocks as live
(and a Mac that throttles timers stretches the run; the virtual clock never does).
"before" puts back the pre-S1 wake thresholds (spot only after 0.3 s, speculate from 0.35 s).
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import faulthandler  # noqa: E402
import json  # noqa: E402
import signal  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from tests.evals.spotter_compare import CLIP_ROOT, NEGATIVES, UNLABELLED, WAKES  # noqa: E402
from zoya import (  # noqa: E402
    audio,
    events,
    orchestrator,
    overlay,
    safety,
    speculate,
    speech,
    tasks,
    voice,
)

RATE = 16000
LEAD_S = 3.5
TAIL_S = 2.0
CLIP_TIMEOUT_S = 60
NOISE_RMS = 0.002
P90 = 90
RESULTS = Path(__file__).parent / "results" / "listen_audio.json"
TASK = SimpleNamespace(id="busy", name="background job", shared=False, command="background job")


class World:
    def __init__(self) -> None:
        self.log: list[dict] = []
        self.dispatched: list[str] = []
        self.stops = 0
        self.busy = False

    def install(self) -> None:
        engine = SimpleNamespace(
            one_shot_at=0.0,
            silence_all=lambda: None,
            set_speech_gain=lambda _g: None,
            clear_speech=lambda: None,
            speech_pending=lambda: False,
        )
        audio.engine = lambda: engine
        audio.duck = audio.restore = lambda: None
        audio.earcon = lambda _name: None
        audio.is_ducked = lambda: False
        speech.narrate = lambda *_a, **_k: None
        speech.is_speaking = lambda: False
        speech.cancel = lambda: None
        events.emit = lambda _e: None
        overlay.level = lambda _b: None
        speculate.prepare = lambda _t: 0
        speculate.discard = lambda: None
        speculate.peek = lambda _t: None
        voice.decisions.ask = lambda *_a, **_k: None
        voice._log_voice = self.log.append
        voice.push_to_talk_held = lambda: False
        voice.time = CLOCK
        tasks.running = lambda: [TASK] if self.busy else []
        orchestrator.start_task = self._start
        orchestrator.stop_task = self._stop

    def _start(self, text: str, *_a, **_k) -> SimpleNamespace:
        self.dispatched.append(text)
        return SimpleNamespace(shared=False)

    def _stop(self, _name: str = "") -> str:
        self.stops += 1
        return orchestrator.STOPPED_MESSAGE


class VirtualClock:
    """Audio time for the loop: each block arrives on its own schedule, and whatever the loop
    computes in between adds its real (perf_counter) duration. The OS timer never matters, so a
    throttled or dozing Mac measures the same as an idle one; GPU contention stays real."""

    def __init__(self) -> None:
        self._virtual, self._real = 0.0, time.perf_counter()

    def monotonic(self) -> float:
        return self._virtual + (time.perf_counter() - self._real)

    def monotonic_ns(self) -> int:
        return int(self.monotonic() * 1e9)

    def arrive(self, at: float) -> None:
        if REAL_TIME and (lag := at - self.monotonic()) > 0:
            time.sleep(lag)
        self._virtual, self._real = max(self.monotonic(), at), time.perf_counter()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


CLOCK = VirtualClock()
REAL_TIME = "realtime" in sys.argv


def feed(loop: voice.VoiceLoop, samples: np.ndarray) -> None:
    blocks = samples[: len(samples) // voice.VAD_BLOCK * voice.VAD_BLOCK]
    started = CLOCK.monotonic()
    for index, block in enumerate(blocks.reshape(-1, voice.VAD_BLOCK)):
        due = started + (index + 1) * voice.BLOCK_S
        CLOCK.arrive(due)
        loop._on_block(due, block.astype(np.float32))


def run_clip(models: voice.Models, world: World, clip: np.ndarray, busy: bool) -> dict:
    world.log.clear()
    world.dispatched.clear()
    world.stops, world.busy = 0, busy
    safety._channel = None
    loop = voice.VoiceLoop(models=models)
    rng = np.random.default_rng(0)
    noise = lambda s: (rng.standard_normal(int(s * RATE)) * NOISE_RMS).astype("f4")  # noqa: E731
    faulthandler.dump_traceback_later(CLIP_TIMEOUT_S, exit=True)
    feed(loop, np.concatenate([noise(LEAD_S), clip, noise(TAIL_S)]))
    faulthandler.cancel_dump_traceback_later()
    wakes = [r for r in world.log if r.get("event") == "wake"]
    stops = [r for r in world.log if r.get("event") == "stop"]
    return {
        "woke": bool(wakes),
        "earcon_ms": wakes[0]["phrase_end_to_earcon_ms"] if wakes else None,
        "stopped": bool(stops) or world.stops > 0,
        "stop_ms": stops[0]["last_voice_to_silence_ms"] if stops else None,
        "dispatched": len(world.dispatched),
    }


def load(folder: str, number: int) -> np.ndarray:
    samples, rate = sf.read(CLIP_ROOT / folder / f"{number:03d}.wav", dtype="float32")
    if rate != RATE:
        raise ValueError(f"{folder}/{number} is {rate} Hz")
    return samples


def summarise(rows: dict[str, dict]) -> dict:
    wake_keys = [f"{f}/{n}" for f, numbers in WAKES.items() for n in numbers]
    negative_keys = [f"{f}/{n}" for f, numbers in NEGATIVES.items() for n in numbers]
    stop_keys = [key for key in rows if key.startswith("stop_clips/")]
    earcons = [rows[k]["earcon_ms"] for k in wake_keys if rows[k]["earcon_ms"] is not None]
    stop_ms = [rows[k]["stop_ms"] for k in stop_keys if rows[k]["stop_ms"] is not None]
    return {
        "wake_to_earcon_p50_ms": round(float(np.percentile(earcons, 50))) if earcons else None,
        "wake_to_earcon_p90_ms": round(float(np.percentile(earcons, P90))) if earcons else None,
        "wakes": f"{sum(rows[k]['woke'] for k in wake_keys)}/{len(wake_keys)}",
        "missed": [k for k in wake_keys if not rows[k]["woke"]],
        "false_wakes": [k for k in negative_keys if rows[k]["woke"]],
        "negatives": len(negative_keys),
        "stops": f"{sum(rows[k]['stopped'] for k in stop_keys)}/{len(stop_keys)}",
        "stop_p50_ms": round(float(np.percentile(stop_ms, 50))) if stop_ms else None,
    }


def main(argv: list[str]) -> int:
    label = "-".join(argv) if argv else "run"
    if "before" in argv:
        voice.WAKE_EARLY_SILENCE_S, voice.WAKE_SPECULATION_MIN_S = voice.WAKE_END_SILENCE_S, 0.0
    faulthandler.register(signal.SIGUSR1, all_threads=True)
    world = World()
    world.install()
    models = voice.load_models()
    rows: dict[str, dict] = {}
    labelled = {f: [*WAKES[f], *NEGATIVES[f], *UNLABELLED[f]] for f in WAKES}
    for folder, numbers in labelled.items():
        for number in sorted(numbers):
            rows[f"{folder}/{number}"] = run_clip(models, world, load(folder, number), busy=False)
            print("CLIP", folder, number, rows[f"{folder}/{number}"], flush=True)
    for path in sorted((CLIP_ROOT / "stop_clips").glob("*.wav")):
        clip = load("stop_clips", int(path.stem))
        rows[f"stop_clips/{int(path.stem)}"] = run_clip(models, world, clip, busy=True)
    summary = summarise(rows)
    print(json.dumps(summary, indent=1))
    saved = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    saved[label] = {"summary": summary, "clips": rows}
    RESULTS.write_text(json.dumps(saved, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
