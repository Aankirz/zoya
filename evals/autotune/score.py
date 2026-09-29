"""Harness runs as autotune reads them, and the cost bar a candidate must hold.

A run is the JSON list `evals/harness/run.py` writes to logs/harness/LABEL.json, one object per
task. Standard library only; never imports zoya.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_CENTS_PER_SUCCESS_RATIO = 1.15  # a candidate may cost at most 15% more on passing tasks


def load(path: Path | str) -> list[dict]:
    """The task objects of one harness run."""
    runs = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise ValueError(f"{path}: expected a JSON list of task objects")
    return runs
