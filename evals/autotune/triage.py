"""Autotune v2 prototype: per-task history, failure triage and the paired keep rule.

Reads the JSON lists `evals/harness/run.py` writes (one `Run` per task) and never runs anything.
Tasks are near-deterministic, so a candidate is judged task by task against that task's own
recent history on main, not by the mean of a whole run. See evals/autotune/design/v2-proposal.md.
Standard library only; never imports zoya.
"""

from __future__ import annotations

import re

WINDOW = 6  # the newest main runs per task that count as its history
MIN_HISTORY = 3
BROKEN_AT_MOST = 1 / 3  # a task passing this share of its history or less is broken
SOLID_AT_LEAST = 5 / 6  # a task passing this share of its history or more is solid
FIX_PASSES = 2  # a fix passes a broken target at least this often...
FIX_RUNS = 3  # ...out of this many candidate runs
MAX_CENTS_RATIO = 1.15  # v1's 15% cost bar (score.py), per run of a solid task
EPSILON = 1e-9

SOLID, BROKEN, FLAKY, NEW = "solid", "broken", "flaky", "new"
_WALL = re.compile(r"\bsign(?:ing)?[ -]?in\b|\blog(?:ging)?[ -]?in\b|\bcaptcha\b", re.I)


def history(main_runs: list[list[dict]]) -> dict[str, list[dict]]:
    """Each task's newest WINDOW runs on main, oldest first. `main_runs` is oldest first."""
    by_task: dict[str, list[dict]] = {}
    for runs in main_runs:
        for run in runs:
            by_task.setdefault(run["id"], []).append(run)
    return {task: runs[-WINDOW:] for task, runs in by_task.items()}


def pass_rate(runs: list[dict]) -> float:
    return sum(run["success"] is True for run in runs) / len(runs) if runs else 0.0


def state(runs: list[dict]) -> str:
    """solid, broken or flaky from a task's history; new until it has MIN_HISTORY runs."""
    if len(runs) < MIN_HISTORY:
        return NEW
    rate = pass_rate(runs)
    if rate >= SOLID_AT_LEAST - EPSILON:
        return SOLID
    if rate <= BROKEN_AT_MOST + EPSILON:
        return BROKEN
    return FLAKY


def cause(task: dict, run: dict) -> str:
    """Why one run failed, read only from what run.py recorded. `task` is its tasks.json entry."""
    if run["success"] is True:
        return "pass"
    error = run.get("error") or ""
    if error.startswith("over "):
        return "timeout"
    if error:
        return "crash"
    said = " ".join(run.get("said") or [])
    asked = run.get("confirmations") or []
    failed = " ".join(run.get("failed_checks") or [])
    if task.get("stakes"):
        if not asked:
            return "never-reached-gate"
        if '"confirm"' in failed:
            return "ask-wording"
    elif asked:
        return "false-ask"
    if _WALL.search(said):
        return "wall"  # a sign-in page or captcha: flag the task's validity, do not tune it
    if '"url"' in failed:
        return "wrong-page"
    return "wrong-answer"


def decide(
    base: dict[str, list[dict]], candidate: dict[str, list[dict]], targets: list[str]
) -> tuple[str, str]:
    """("keep" | "discard" | "rerun", reason) for a branch aimed at `targets`.

    keep: some broken target passes FIX_PASSES of FIX_RUNS or more, no solid task fails more than
    once in three, and the solid tasks cost at most 15% more per run than in their history.
    rerun: a solid task failed once in fewer than FIX_RUNS runs, so it needs
    runs before anything is concluded.
    """
    rerun = []
    for task, runs in sorted(candidate.items()):
        if state(base.get(task, [])) != SOLID:
            continue
        fails = sum(run["success"] is not True for run in runs)
        if fails >= 2:
            return "discard", f"{task} was solid and failed {fails} of {len(runs)}"
        if fails == 1 and len(runs) < FIX_RUNS:
            rerun.append(task)
    if rerun:
        return "rerun", f"solid tasks failed once: {', '.join(rerun)}"

    fixed = []
    for task in targets:
        runs = candidate.get(task, [])
        if state(base.get(task, [])) != BROKEN or len(runs) < FIX_RUNS:
            continue
        if sum(run["success"] is True for run in runs) >= FIX_PASSES:
            fixed.append(task)
    if not fixed:
        return "discard", f"no broken target passed {FIX_PASSES} of {FIX_RUNS}"

    solid = [task for task in candidate if state(base.get(task, [])) == SOLID]
    base_cents = _mean_cents([run for task in solid for run in base[task]])
    cand_cents = _mean_cents([run for task in solid for run in candidate[task]])
    if cand_cents > base_cents * MAX_CENTS_RATIO + EPSILON:
        return "discard", f"solid tasks' cents per run {base_cents:.2f} → {cand_cents:.2f}"
    return "keep", f"fixed {', '.join(fixed)}; solid tasks held"


def _mean_cents(runs: list[dict]) -> float:
    return sum(run["cents"] for run in runs) / len(runs) if runs else 0.0
