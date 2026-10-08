"""Wake/stop spotter comparison on the owner's real clips: Whisper base.en (mlx) vs Cactus Whistle.

D160: Whistle is a candidate for the always-on wake/stop spotter only. This scores both engines on
the same audio with the same parser (zoya.voice.is_wake / is_stop) and reports latency per call.

Two steps, because Whistle is not a Zoya dependency:
1. In any venv with `cactus-needle`, numpy and soundfile (no zoya imports):
     NEEDLE_TELEMETRY=0 python tests/evals/spotter_compare.py whistle OUT.json [KEYWORD,...]
2. In the project venv (scores base.en live and the Whistle dump):
     .venv/bin/python -u -m tests.evals.spotter_compare score OUT.json [OUT2.json ...]

Clips are local only (logs/ is git-ignored); free chatter is never printed.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

CLIP_ROOT = Path(os.environ.get("ZOYA_CLIP_ROOT", Path.home() / "Desktop/zoya/logs"))
RATE = 16000
WAKE_WINDOW_S = 2.5
STOP_WINDOW_S = 2.0
REPEATS = 3
MS_PER_S = 1000
P90 = 90
FOLDERS = {
    "wake_clips": WAKE_WINDOW_S,
    "wake_clips_session2": WAKE_WINDOW_S,
    "stop_clips": STOP_WINDOW_S,
}
# Labels: wake_sweep.py (session 2) and aec_replay.py (session 1); 3, 6, 8, 9 of session 1 were
# never labelled, so they are reported apart and kept out of the counts.
WAKES = {
    "wake_clips_session2": [1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13],
    "wake_clips": [1, 2, 4, 5, 7, 10, 11, 12, 15, 17],
}
NEGATIVES = {
    "wake_clips_session2": list(range(14, 31)),
    "wake_clips": [13, 14, 16, 18, 19, 20, 21],
}
UNLABELLED = {"wake_clips": [3, 6, 8, 9], "wake_clips_session2": [7, 10]}
PRIVATE = {("wake_clips_session2", 29), ("wake_clips_session2", 30)}


def clips() -> list[tuple[str, int, object]]:
    import soundfile as sf

    found = []
    for folder, seconds in FOLDERS.items():
        for path in sorted((CLIP_ROOT / folder).glob("*.wav")):
            samples, rate = sf.read(path, dtype="float32")
            if rate != RATE:
                raise ValueError(f"{path} is {rate} Hz")
            found.append((folder, int(path.stem), samples[: int(seconds * rate)]))
    return found


def timed(transcribe, samples) -> tuple[str, float]:
    runs, text = [], ""
    for _ in range(REPEATS):
        started = time.perf_counter()
        text = transcribe(samples)
        runs.append((time.perf_counter() - started) * MS_PER_S)
    return text, sorted(runs)[len(runs) // 2]


def dump_whistle(out: Path, keywords: list[str]) -> None:
    import numpy as np
    from needle.agent.whistle import Whistle

    model = Whistle()

    def transcribe(samples) -> str:
        return model.transcribe(samples, language="en", keywords=keywords)["text"]

    transcribe(np.zeros(RATE, np.float32))
    rows = {}
    for folder, number, samples in clips():
        text, ms = timed(transcribe, samples)
        rows[f"{folder}/{number}"] = {"text": text, "ms": ms}
    out.write_text(json.dumps({"engine": f"whistle keywords={keywords}", "rows": rows}, indent=1))


def dump_base_en() -> dict:
    from zoya.config import WAKE_MODEL
    from zoya.voice import load_whisper

    spot = load_whisper(WAKE_MODEL, language="en", initial_prompt="Zoya")
    rows = {}
    for folder, number, samples in clips():
        text, ms = timed(spot, samples)
        rows[f"{folder}/{number}"] = {"text": text, "ms": ms}
    return {"engine": "mlx whisper base.en prompt=Zoya", "rows": rows}


def score(dump: dict) -> dict:
    import numpy as np

    from zoya.voice import is_stop, is_wake

    rows = dump["rows"]

    def heard(folder: str, number: int) -> str:
        return rows[f"{folder}/{number}"]["text"]

    wakes = [(f, n) for f, numbers in WAKES.items() for n in numbers]
    negatives = [(f, n) for f, numbers in NEGATIVES.items() for n in numbers]
    stops = [key for key in rows if key.startswith("stop_clips/")]
    latencies = [row["ms"] for row in rows.values()]
    missed = {f"{f}/{n}": heard(f, n) for f, n in wakes if not is_wake(heard(f, n))}
    false = {
        f"{f}/{n}": "<chatter>" if (f, n) in PRIVATE else heard(f, n)
        for f, n in negatives
        if is_wake(heard(f, n))
    }
    stop_missed = {key: rows[key]["text"] for key in stops if not is_stop(rows[key]["text"])}
    unlabelled = {f"{f}/{n}": heard(f, n) for f, numbers in UNLABELLED.items() for n in numbers}
    return {
        "engine": dump["engine"],
        "p50_ms": round(float(np.percentile(latencies, 50)), 1),
        "p90_ms": round(float(np.percentile(latencies, P90)), 1),
        "wakes": f"{len(wakes) - len(missed)}/{len(wakes)}",
        "false_wakes": f"{len(false)}/{len(negatives)}",
        "stops": f"{len(stops) - len(stop_missed)}/{len(stops)}",
        "missed": missed,
        "false": false,
        "stop_missed": stop_missed,
        "unlabelled_heard": unlabelled,
    }


def main(argv: list[str]) -> int:
    if argv[:1] == ["whistle"]:
        keywords = argv[2].split(",") if len(argv) > 2 else ["Zoya"]
        dump_whistle(Path(argv[1]), keywords)
        return 0
    if argv[:1] != ["score"]:
        print(__doc__)
        return 2
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    dumps = [dump_base_en(), *(json.loads(Path(p).read_text()) for p in argv[1:])]
    for dump in dumps:
        print(json.dumps(score(dump), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
