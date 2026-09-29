"""Per-task history and the keep rule: each task is judged against its own recent census runs.

Harness tasks are close to deterministic (night 1: most passed 0/18 or 16-18/18), so a candidate
is judged task by task, not by a group's mean. Standard library only; never imports zoya.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from evals.autotune.score import MAX_CENTS_PER_SUCCESS_RATIO

WINDOW = 6  # the newest census runs of a task that make its class
MIN_SAMPLES = 3  # fewer census runs than this and the task is NEW
SLACK_PER = 6  # at most one run in six may go the other way for PASS or FAIL
TARGET_RUNS = 3  # a declared target runs this many times
FIX_PASSES = 2  # a FAIL target passing this many of TARGET_RUNS is fixed
BREAK_FAILS = 2  # a PASS sentinel failing this many of TARGET_RUNS is broken
SENTINEL_RERUNS = 2  # a PASS sentinel that failed its one run runs this many more times

PASS, FAIL, FLAKY, NEW, NEW_FAIL = "PASS", "FAIL", "FLAKY", "NEW", "NEW-FAIL"
PROVEN, CONSISTENT, REJECTED = "proven", "consistent", "rejected"


@dataclass(frozen=True)
class Outcome:
    success: bool
    cents: float = 0.0


@dataclass
class Verdict:
    status: str
    fixed: list[str] = field(default_factory=list)
    broken: list[str] = field(default_factory=list)
    held_out_broken: list[str] = field(default_factory=list)
    not_judged: list[str] = field(default_factory=list)
    reason: str = ""


def classify(outcomes: list[Outcome]) -> str:
    """PASS or FAIL when at most one run in six of the newest WINDOW went the other way, FLAKY
    otherwise, NEW with fewer than MIN_SAMPLES."""
    recent = outcomes[-WINDOW:]
    if len(recent) < MIN_SAMPLES:
        return NEW
    passes = sum(o.success for o in recent)
    slack = len(recent) // SLACK_PER
    if len(recent) - passes <= slack:
        return PASS
    if passes <= slack:
        return FAIL
    return FLAKY


def label(before: list[Outcome], tonight: list[Outcome]) -> str:
    """A task's class after tonight's census; NEW-FAIL when it was PASS until tonight's first run
    failed, the regression alarm."""
    if tonight and not tonight[0].success and classify(before) == PASS:
        return NEW_FAIL
    return classify(before + tonight)


def reruns(history: dict[str, list[Outcome]], runs: dict[str, list[Outcome]]) -> list[str]:
    """Sentinels that are PASS on history and failed a run, with fewer than TARGET_RUNS so far."""
    return [
        task
        for task, outcomes in sorted(runs.items())
        if classify(history.get(task, [])) == PASS
        and len(outcomes) < TARGET_RUNS
        and not all(o.success for o in outcomes)
    ]


def verdict(
    history: dict[str, list[Outcome]],
    runs: dict[str, list[Outcome]],
    targets: list[str],
    held_out: set[str],
) -> Verdict:
    """proven: a target fixed, nothing broken, no held-out task broken, cents held. consistent:
    every target passed every run but none is provably fixed (a FLAKY or NEW target). Otherwise
    rejected. FLAKY and NEW sentinels are reported, not judged."""
    result = Verdict(REJECTED)
    base_cents = cand_cents = 0.0
    for task, outcomes in sorted(runs.items()):
        before = history.get(task, [])
        state = classify(before)
        passes = sum(o.success for o in outcomes)
        if task in targets and state == FAIL and _fixed(outcomes):
            result.fixed.append(task)
        elif state == PASS and len(outcomes) - passes >= BREAK_FAILS:
            (result.held_out_broken if task in held_out else result.broken).append(task)
        elif state == PASS and passes:
            base_cents += _mean_paid_cents(before)
            cand_cents += _mean_paid_cents(outcomes)
        elif state in (FLAKY, NEW) and task not in targets and task not in held_out:
            result.not_judged.append(f"{task} {passes}/{len(outcomes)}")
    result.status, result.reason = _decide(history, runs, targets, result, base_cents, cand_cents)
    return result


def _decide(
    history: dict[str, list[Outcome]],
    runs: dict[str, list[Outcome]],
    targets: list[str],
    result: Verdict,
    base_cents: float,
    cand_cents: float,
) -> tuple[str, str]:
    pending = reruns(history, {t: o for t, o in runs.items() if t not in targets})
    short = [t for t in targets if len(runs.get(t, [])) < TARGET_RUNS]
    if pending or short:
        return REJECTED, f"unfinished: reruns missing for {pending}, targets short of runs {short}"
    if result.held_out_broken:
        return REJECTED, f"breaks held-out tasks {result.held_out_broken}"
    if result.broken:
        return REJECTED, f"breaks passing tasks {result.broken}"
    if base_cents and cand_cents > base_cents * MAX_CENTS_PER_SUCCESS_RATIO:
        return REJECTED, f"cents on tasks passing both ways {base_cents:.1f} → {cand_cents:.1f}"
    if result.fixed:
        return PROVEN, f"fixes {result.fixed}"
    if targets and all(all(o.success for o in runs[t]) for t in targets):
        return CONSISTENT, "every target passed every run, but none was FAIL on history"
    return REJECTED, "fixes no target"


def _fixed(outcomes: list[Outcome]) -> bool:
    return len(outcomes) >= TARGET_RUNS and sum(o.success for o in outcomes) >= FIX_PASSES


def _mean_paid_cents(outcomes: list[Outcome]) -> float:
    paid = [o.cents for o in outcomes if o.success]
    return statistics.fmean(paid) if paid else math.inf
