"""Score harness runs and decide whether a candidate beats the baseline.

A run is the JSON list `evals/harness/run.py` writes to logs/harness/LABEL.json, one object per
task. Standard library only; never imports zoya.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

MAX_CENTS_PER_SUCCESS_RATIO = 1.15  # a kept candidate may cost at most 15% more per success
MIN_REPEATS = 2
EPSILON = 1e-9


def load(path: Path | str) -> list[dict]:
    """The task objects of one harness run."""
    runs = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise ValueError(f"{path}: expected a JSON list of task objects")
    return runs


def summarize(runs: list[dict]) -> dict:
    """Successes, totals per group, median seconds and total cents of one harness run."""
    by_group: dict[str, list[int]] = {}
    for run in runs:
        counts = by_group.setdefault(run["group"], [0, 0])
        counts[0] += run["success"] is True
        counts[1] += 1
    return {
        "success": sum(counts[0] for counts in by_group.values()),
        "total": len(runs),
        "by_group": by_group,
        "median_seconds": statistics.median(run["seconds"] for run in runs) if runs else 0.0,
        "cents": sum(run["cents"] for run in runs),
    }


def decide(baseline: list[dict], candidate: list[dict], min_gain: float = 1.0) -> tuple[bool, str]:
    """Keep the candidate only if its mean success gains `min_gain`, no group's mean success
    drops, and its cents per success is at most 15% worse. Both sides are `summarize()` results
    of at least two repeated runs of the same tasks."""
    for side, summaries in (("baseline", baseline), ("candidate", candidate)):
        if len(summaries) < MIN_REPEATS:
            return False, f"the {side} has {len(summaries)} runs; at least {MIN_REPEATS} needed"
    shapes = {_shape(summary) for summary in baseline + candidate}
    if len(shapes) != 1:
        return False, "the runs did not cover the same tasks (totals per group differ)"

    base_success = statistics.fmean(s["success"] for s in baseline)
    cand_success = statistics.fmean(s["success"] for s in candidate)
    if cand_success < base_success + min_gain - EPSILON:
        return False, (
            f"mean success {base_success:.2f} → {cand_success:.2f} gains less than {min_gain:g}"
        )

    for group in sorted(baseline[0]["by_group"]):
        base_group = statistics.fmean(s["by_group"][group][0] for s in baseline)
        cand_group = statistics.fmean(s["by_group"][group][0] for s in candidate)
        if cand_group < base_group - EPSILON:
            return False, f"{group} drops from {base_group:.2f} to {cand_group:.2f} mean successes"

    base_cps = _cents_per_success(baseline)
    cand_cps = _cents_per_success(candidate)
    if cand_cps > base_cps * MAX_CENTS_PER_SUCCESS_RATIO + EPSILON:
        return False, (
            f"cents per success {base_cps:.2f} → {cand_cps:.2f} is more than "
            f"{MAX_CENTS_PER_SUCCESS_RATIO - 1:.0%} worse"
        )

    return True, (
        f"mean success {base_success:.2f} → {cand_success:.2f}, "
        f"cents per success {base_cps:.2f} → {cand_cps:.2f}"
    )


def _shape(summary: dict) -> tuple:
    groups = tuple(sorted((group, counts[1]) for group, counts in summary["by_group"].items()))
    return summary["total"], groups


def _cents_per_success(summaries: list[dict]) -> float:
    """Pooled over the repeats: total cents over total successes (infinite with none)."""
    successes = sum(s["success"] for s in summaries)
    cents = sum(s["cents"] for s in summaries)
    return cents / successes if successes else math.inf
