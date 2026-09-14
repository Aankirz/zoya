"""Wake-word spotter sweep on the owner's real clips (D51 evidence).

Clips come from `python -m zoya.main --test-wake --record-clips` (logs/wake_clips/, git-ignored,
never uploaded). Grid: {mlx, faster-whisper} × {tiny.en, base.en, small.en} × {prompt "Zoya", none},
plus D19's original settings (faster-whisper base.en int8, beam 5, prompt) and a name-confidence
gate from mlx word timestamps. Scored with zoya.voice.is_wake on the first WAKE_WINDOW_S.

Usage: .venv/bin/python -u tests/evals/wake_sweep.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from zoya.config import LOG_DIR, MIC_SAMPLE_RATE_HZ, WAKE_WINDOW_S
from zoya.voice import NAME, is_wake, words

CLIPS = LOG_DIR / "wake_clips"
RESULTS = Path(__file__).parent / "results" / "wake_sweep.json"
# Owner's 2026-09-14 session: 1–13 "Hey Zoya" attempts (7 and 10 are the first halves of split
# attempts 8 and 11, so they may or may not wake); 14–30 negatives and chatter.
WAKES = [1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 13]
FRAGMENTS = [7, 10]
NEGATIVES = list(range(14, 31))
CONFIDENCE_GATES = (0.0, 0.3, 0.5, 0.7)


def load_clips() -> dict[int, np.ndarray]:
    clips = {}
    for number in WAKES + FRAGMENTS + NEGATIVES:
        samples, rate = sf.read(CLIPS / f"{number:03d}.wav", dtype="float32")
        assert rate == MIC_SAMPLE_RATE_HZ
        clips[number] = samples[: int(WAKE_WINDOW_S * rate)]
    return clips


def mlx_spotter(size: str, prompt: bool):
    import mlx.core as mx
    import mlx_whisper
    from mlx_whisper.load_models import load_model
    from mlx_whisper.transcribe import ModelHolder

    repo = f"mlx-community/whisper-{size}.en-mlx"
    model = load_model(repo, dtype=mx.float16)

    def spot(samples: np.ndarray) -> tuple[str, float]:
        ModelHolder.model, ModelHolder.model_path = model, repo
        result = mlx_whisper.transcribe(
            samples,
            path_or_hf_repo=repo,
            language="en",
            initial_prompt="Zoya" if prompt else None,
            temperature=0.0,
            condition_on_previous_text=False,
            word_timestamps=True,
        )
        name_probs = [
            w["probability"]
            for seg in result["segments"]
            for w in seg.get("words", [])
            if any(NAME.match(x) for x in words(w["word"]))
        ]
        return result["text"].strip(), max(name_probs, default=0.0)

    return spot


def cpu_spotter(size: str, prompt: bool, beam: int = 1):
    from faster_whisper import WhisperModel

    model = WhisperModel(f"{size}.en", device="cpu", compute_type="int8")

    def spot(samples: np.ndarray) -> tuple[str, float]:
        segments, _ = model.transcribe(
            samples,
            language="en",
            initial_prompt="Zoya" if prompt else None,
            beam_size=beam,
            vad_filter=False,
        )
        return " ".join(s.text for s in segments).strip(), 1.0

    return spot


def score(name: str, spot, clips: dict[int, np.ndarray]) -> list[dict]:
    spot(clips[WAKES[0]])  # warm up
    heard, latencies = {}, []
    for number, samples in clips.items():
        started = time.monotonic()
        heard[number] = spot(samples)
        latencies.append((time.monotonic() - started) * 1000)
    rows = []
    for gate in CONFIDENCE_GATES:
        woke = {n for n, (text, prob) in heard.items() if is_wake(text) and prob >= gate}
        rows.append(
            {
                "config": name,
                "gate": gate,
                "wakes": f"{len(woke & set(WAKES))}/{len(WAKES)}",
                "false": sorted(woke & set(NEGATIVES)),
                "median_ms": round(float(np.median(latencies))),
                "missed": {n: heard[n][0] for n in WAKES if n not in woke},
            }
        )
        if name.startswith("faster"):
            break  # no word probabilities gathered for the CPU engine
    print(json.dumps(rows[0] | {"false_heard": {n: heard[n][0] for n in rows[0]["false"]}}))
    return rows


def main() -> int:
    clips = load_clips()
    configs = [("faster-whisper base.en beam5 prompt (D19 original)", cpu_spotter("base", True, 5))]
    for size in ("tiny", "base", "small"):
        for prompt in (True, False):
            label = f"{size}.en {'prompt' if prompt else 'no-prompt'}"
            configs.append((f"mlx {label}", mlx_spotter(size, prompt)))
            configs.append((f"faster-whisper {label}", cpu_spotter(size, prompt)))
    rows = [row for name, spot in configs for row in score(name, spot, clips)]
    RESULTS.write_text(json.dumps(rows, indent=1))
    print(f"\n{'config':52} gate wakes  false median_ms")
    for r in rows:
        false = len(r["false"])
        print(f"{r['config']:52} {r['gate']:.1f}  {r['wakes']:6} {false:>3}  {r['median_ms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
