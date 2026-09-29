"""Grading a harness run against its task's checks: pure, so saved runs regrade on Linux.

    python evals/harness/grade.py RUNS.json [--tasks evals/harness/tasks.json]

`run.py` grades live runs with `failed_checks` and a real shell; `regrade` grades a saved run
again without one, keeping the recorded result of its shell checks. Standard library only; never
imports zoya.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

TASKS_FILE = Path(__file__).with_name("tasks.json")
SHELL_KEY = '"shell"'


def failed_checks(
    task: Mapping[str, Any],
    said: list[str],
    confirmations: list[str],
    url: str,
    token: str,
    shell: Callable[[str], str],
) -> list[str]:
    """Each of the task's checks this transcript fails, as its JSON."""
    heard = " ".join(said)
    asked = " ".join(confirmations)
    failed = []
    for check in task["checks"]:
        pattern = {k: v.replace("{token}", token) for k, v in check.items() if isinstance(v, str)}
        if "said" in check:
            ok = len(re.findall(pattern["said"], heard, re.I)) >= check.get("min", 1)
        elif "not_said" in check:
            ok = not re.search(pattern["not_said"], heard, re.I)
        elif "confirm" in check:
            ok = bool(re.search(pattern["confirm"], asked, re.I))
        elif "url" in check:
            ok = bool(re.search(pattern["url"], url, re.I))
        else:
            ok = bool(re.search(pattern["match"], shell(pattern["shell"]), re.I))
        if not ok:
            failed.append(json.dumps(check, ensure_ascii=False))
    return failed


def regrade(task: Mapping[str, Any], run: Mapping[str, Any]) -> list[str]:
    """The saved run's failed checks under the task's current checks. Checks that read the
    transcript (said, asked, url) are graded again; shell checks keep their recorded result."""
    replayable = {**task, "checks": [c for c in task["checks"] if "shell" not in c]}
    kept_shell = [c for c in run["failed_checks"] if SHELL_KEY in c]
    fresh = failed_checks(replayable, run["said"], run["confirmations"], run["url"], "", _no_shell)
    return fresh + kept_shell


def load_tasks(path: Path = TASKS_FILE) -> dict[str, dict[str, Any]]:
    return {task["id"]: task for task in json.loads(path.read_text(encoding="utf-8"))}


def regrade_file(runs_file: Path, tasks_file: Path = TASKS_FILE) -> list[dict[str, Any]]:
    """Every saved run in `runs_file` with `failed_checks` and `success` graded again."""
    tasks = load_tasks(tasks_file)
    graded = []
    for run in json.loads(runs_file.read_text(encoding="utf-8")):
        failed = regrade(tasks[run["id"]], run)
        graded.append({**run, "failed_checks": failed, "success": not failed and not run["error"]})
    return graded


def _no_shell(command: str) -> str:
    raise ValueError(f"regrade runs no shell: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    parser.add_argument("--tasks", type=Path, default=TASKS_FILE)
    args = parser.parse_args(argv)
    runs = regrade_file(args.runs, args.tasks)
    for run in runs:
        print(f"{'PASS' if run['success'] else 'FAIL'} {run['id']} {run['failed_checks']}")
    print(f"{sum(run['success'] for run in runs)}/{len(runs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
