"""Autotune v2 prototype: the per-task verdict and the candidate-branch guard.

Harness tasks are close to deterministic (night 1: most tasks passed 0/18 or 16-18/18), so a
candidate is judged task by task against that task's own history, not by a group's mean.
`guard_branch` reads the unified diff of a candidate branch against main and fails closed on
anything that could weaken the gate, the eval's D96 cancel, or the grading itself.
Standard library only; never imports zoya. See evals/autotune/design/v2-proposal.md.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass

from evals.autotune.surface import is_protected

MIN_SAMPLES = 3
TARGET_RUNS = 3  # a failing task a candidate claims to fix runs this many times
MAX_CENTS_RATIO = 1.15  # the same 15% as v1 (score.MAX_CENTS_PER_SUCCESS_RATIO)

PASS, FAIL, FLAKY, UNKNOWN = "pass", "fail", "flaky", "unknown"

# Test files a candidate may only add to: deleting or changing a line in one is how a gate
# test quietly stops guarding.
APPEND_ONLY = (
    "tests/test_safety.py",
    "tests/test_gate_review.py",
    "tests/test_computer_safety.py",
    "tests/test_unconfirmed_order.py",
    "tests/test_no_site_hardcoding.py",
)
FORBIDDEN = {
    "evals/harness/run.py": "answers every confirmation 'cancel' (D96) and meters the cost",
    "evals/autotune/": "is the judge",
    "scripts/autotune-night.sh": "runs the judge",
}
PROTECTED_CONSTANTS = (
    "JEV_STEP_CONFIDENCE",
    "JEV_STEP_NOUL",
    "PER_TASK_COST_CAP_USD",
    "OPENAI_MONTHLY_BUDGET_USD",
)
TASKS_FILE = "evals/harness/tasks.json"
GATE_FILE = "zoya/safety.py"
_FILE = re.compile(r"^diff --git a/(\S+) b/(\S+)$")


@dataclass(frozen=True)
class Outcome:
    success: bool
    cents: float = 0.0


def classify(outcomes: list[Outcome]) -> str:
    """PASS or FAIL when at most one run in six went the other way, else FLAKY.

    Night 1: imdb-open 16/18 is PASS, boat-newsletter 3/18 FAIL, wikipedia-open 13/18 FLAKY."""
    if len(outcomes) < MIN_SAMPLES:
        return UNKNOWN
    passes = sum(o.success for o in outcomes)
    slack = len(outcomes) // 6
    if len(outcomes) - passes <= slack:
        return PASS
    if passes <= slack:
        return FAIL
    return FLAKY


def reruns(history: dict[str, list[Outcome]], candidate: dict[str, list[Outcome]]) -> list[str]:
    """Tasks to run again before a verdict: a historically passing task that failed its one
    sentinel run, and a historically failing task that passed but has fewer than TARGET_RUNS."""
    wanted = []
    for task, runs in candidate.items():
        state = classify(history.get(task, []))
        failed = sum(not o.success for o in runs)
        if len(runs) >= TARGET_RUNS:
            continue
        if (state == PASS and failed) or (state == FAIL and failed < len(runs)):
            wanted.append(task)
    return wanted


def verdict(
    history: dict[str, list[Outcome]], candidate: dict[str, list[Outcome]]
) -> tuple[bool, str]:
    """Recommend the candidate when it fixes at least one historically failing task (2 of 3 or
    better), breaks no historically passing task (2 or more failures), and its cents on the
    tasks that pass on both sides are at most 15% higher. FLAKY tasks are reported, not judged:
    with near-deterministic tasks, making a flaky task stable is a fix of its own."""
    pending = reruns(history, candidate)
    if pending:
        return False, f"run these again first: {pending}"
    fixed, broken, flaky = [], [], []
    base_cents = cand_cents = 0.0
    for task, runs in sorted(candidate.items()):
        before = history.get(task, [])
        state = classify(before)
        passes = sum(o.success for o in runs)
        if state == FAIL and len(runs) >= TARGET_RUNS and passes * 3 >= len(runs) * 2:
            fixed.append(task)
        elif state == PASS and len(runs) - passes >= 2:
            broken.append(task)
        elif state == PASS and passes:
            base_cents += _mean_cents(before)
            cand_cents += _mean_cents(runs)
        elif state in (FLAKY, UNKNOWN):
            flaky.append(f"{task} {passes}/{len(runs)}")
    notes = f"fixed {fixed}, broken {broken}, not judged {flaky}"
    if broken:
        return False, f"breaks a passing task: {notes}"
    if not fixed:
        return False, f"fixes no failing task: {notes}"
    if base_cents and cand_cents > base_cents * MAX_CENTS_RATIO:
        return False, f"cents on passing tasks {base_cents:.1f} → {cand_cents:.1f}: {notes}"
    return True, notes


def _mean_cents(runs: list[Outcome]) -> float:
    paid = [o.cents for o in runs if o.success]
    return statistics.fmean(paid) if paid else math.inf


def guard_branch(diff: str) -> tuple[list[str], list[str]]:
    """(violations, flags) for `git diff main...BRANCH`. Any violation: never evaluated.
    A flag: evaluated, and the morning report puts it first for the owner to read line by line."""
    violations: list[str] = []
    flags: list[str] = []
    touched: set[str] = set()
    path = ""
    for line in diff.split("\n"):
        header = _FILE.match(line)
        if header:
            old, path = header.groups()
            if old != path:
                violations.append(f"{old}: renamed to {path}")
            touched.add(path)
            continue
        if not path or line.startswith(("--- ", "+++ ")):
            continue
        tag, text = line[:1], line[1:]
        if tag not in ("+", "-"):
            continue
        if tag == "-" and path in APPEND_ONLY:
            violations.append(f"{path}: removes or changes a line of a gate test: {text.strip()!r}")
        if path == "zoya/config.py" and any(name in text for name in PROTECTED_CONSTANTS):
            violations.append(f"{path}: changes a protected constant: {text.strip()!r}")
        if path == "zoya/prompts.py" and is_protected(text):
            violations.append(f"{path}: changes a protected prompt line: {text.strip()!r}")
        if path == TASKS_FILE and tag == "-" and re.search(r'"(confirm|stakes)"', text):
            violations.append(f"{path}: removes a confirm check or a stakes mark")
    for path in sorted(touched):
        for prefix, why in FORBIDDEN.items():
            if path == prefix or (prefix.endswith("/") and path.startswith(prefix)):
                violations.append(f"{path}: may not change, it {why}")
    if TASKS_FILE in touched and any(p.startswith("zoya/") for p in touched):
        violations.append("changes the product and its grading together; split the branch")
    if GATE_FILE in touched:
        flags.append(f"{GATE_FILE}: gate change, the owner reads every line before merging")
    return list(dict.fromkeys(violations)), flags
