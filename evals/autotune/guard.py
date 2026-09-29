"""The guard every candidate branch passes before a night runs it.

`check` reads `git diff --no-renames BASE...SHA` and fails closed: a violation means the branch is
never pinned or run. A flag means it may run, and the review reads that change first.
Standard library only; never imports zoya.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from evals.autotune.surface import is_protected

MAX_CHANGED_LINES = 400  # outside tests/fixtures/, so the review stays a real review
TASKS_FILE = "evals/harness/tasks.json"
PROMPTS_FILE = "zoya/prompts.py"
PRODUCT_DIR = "zoya/"
TESTS_DIR = "tests/"
FIXTURES_DIR = "tests/fixtures/"
CONFTEST = "conftest.py"
REFUSED_FILES = {
    "evals/harness/run.py": "is the harness, which answers every confirmation 'cancel' (D96)",
    "evals/harness/grade.py": "grades the harness runs",
    "Makefile": "holds `make check`, which judges the candidate",
}
REFUSED_PREFIXES = {
    "evals/autotune/": "is the judge",
    "scripts/autotune-": "runs the judge",
}
PROTECTED_CONSTANTS = (
    "JEV_STEP_CONFIDENCE",
    "JEV_STEP_NOUL",
    "PER_TASK_COST_CAP_USD",
    "OPENAI_MONTHLY_BUDGET_USD",
)
FLAGGED_FILES = ("zoya/safety.py", "zoya/speech.py")
GUARD_2_CALLS = (
    "click_checked",
    "risky_label",
    "click_risk",
    "native_click_risk",
    "native_input_blocked",
    "require_confirmation",
)
SITE_NAMES = (
    "flipkart",
    "ebay",
    "bandcamp",
    "goodreads",
    "imdb",
    "wikipedia",
    "boat-lifestyle",
    "amazon",
    "booking.com",
    "youtube",
    "spotify",
)
TASK_MARKS = ("stakes", "held_out")

_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
_BAD_HEADERS = {
    "old mode": "changes a file mode",
    "new mode": "changes a file mode",
    "GIT binary patch": "is a binary patch",
    "Binary files": "is a binary patch",
}
_SITE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(name) for name in SITE_NAMES) + r")(?![a-z0-9])",
    re.I,
)


@dataclass
class Result:
    violations: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


@dataclass
class _File:
    path: str
    new: bool = False
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


def check(diff: str, tasks_before: str | None = None, tasks_after: str | None = None) -> Result:
    """Every violation and flag of a candidate's diff. `tasks_before` and `tasks_after` are
    tasks.json at the base and at the candidate, needed when the diff touches it."""
    files, violations = _parse(diff)
    result = Result(violations)
    for changed in files:
        result.violations += _path_violations(changed) + _line_violations(changed)
        result.flags += _flags(changed)
    paths = {changed.path for changed in files}
    if TASKS_FILE in paths:
        result.violations += _task_violations(tasks_before, tasks_after)
        if any(path.startswith(PRODUCT_DIR) for path in paths):
            result.violations.append("changes the product and its grading together; split it")
    changed_lines = sum(
        len(f.added) + len(f.removed) for f in files if not f.path.startswith(FIXTURES_DIR)
    )
    if changed_lines > MAX_CHANGED_LINES:
        result.violations.append(f"{changed_lines} changed lines; at most {MAX_CHANGED_LINES}")
    result.violations = list(dict.fromkeys(result.violations))
    result.flags = list(dict.fromkeys(result.flags))
    return result


def check_targets(targets: list[str], task_ids: set[str], held_out: set[str]) -> list[str]:
    """Why the declared Autotune-Targets cannot be run, if they cannot."""
    if not targets:
        return ["declares no Autotune-Targets trailer"]
    violations = []
    unknown = sorted(set(targets) - task_ids)
    if unknown:
        violations.append(f"targets unknown tasks {unknown}")
    hidden = sorted(set(targets) & held_out)
    if hidden:
        violations.append(f"targets held-out tasks {hidden}")
    return violations


def _parse(diff: str) -> tuple[list[_File], list[str]]:
    files: list[_File] = []
    in_hunk = False
    for number, line in enumerate(diff.split("\n"), 1):
        if line.startswith("diff --git "):
            header = _HEADER.match(line)
            if not header or header.group(1) != header.group(2) or '"' in line:
                return files, [f"line {number}: cannot read the header {line!r}"]
            files.append(_File(header.group(2)))
            in_hunk = False
        elif not files:
            if line:
                return files, [f"line {number}: expected 'diff --git', got {line!r}"]
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            files[-1].added.append(line[1:])
        elif in_hunk and line.startswith("-"):
            files[-1].removed.append(line[1:])
        elif line.startswith("new file mode"):
            files[-1].new = True
        elif reason := _bad_header(line):
            return files, [f"{files[-1].path}: the diff {reason}"]
    return files, []


def _bad_header(line: str) -> str | None:
    for header, reason in _BAD_HEADERS.items():
        if line.startswith(header):
            return reason
    return None


def _path_violations(changed: _File) -> list[str]:
    path = changed.path
    if path in REFUSED_FILES:
        return [f"{path}: may not change, it {REFUSED_FILES[path]}"]
    for prefix, why in REFUSED_PREFIXES.items():
        if path.startswith(prefix):
            return [f"{path}: may not change, it {why}"]
    if path.rsplit("/", 1)[-1] == CONFTEST:
        return [f"{path}: a conftest.py may not change or be added"]
    if path.startswith(TESTS_DIR) and not changed.new:
        return [f"{path}: existing tests are read-only"]
    return []


def _line_violations(changed: _File) -> list[str]:
    path = changed.path
    violations = []
    for line in changed.added + changed.removed:
        if not path.startswith(TESTS_DIR) and any(name in line for name in PROTECTED_CONSTANTS):
            violations.append(f"{path}: changes a protected constant: {line.strip()!r}")
        if path == PROMPTS_FILE and is_protected(line):
            violations.append(f"{path}: changes a protected prompt line: {line.strip()!r}")
    if path.startswith(PRODUCT_DIR):
        for line in changed.added:
            if _SITE.search(line):
                violations.append(f"{path}: adds a site name: {line.strip()!r}")
    return violations


def _flags(changed: _File) -> list[str]:
    if changed.path in FLAGGED_FILES:
        return [f"{changed.path}: changes the gate or the voice; read every line"]
    if not changed.path.startswith(PRODUCT_DIR):
        return []
    calls = [
        line.strip()
        for line in changed.added + changed.removed
        if any(call in line for call in GUARD_2_CALLS)
    ]
    return [f"{changed.path}: changes a Guard 2 call site: {line!r}" for line in calls]


def _task_violations(before_text: str | None, after_text: str | None) -> list[str]:
    try:
        before = {task["id"]: task for task in json.loads(before_text or "")}
        after = {task["id"]: task for task in json.loads(after_text or "")}
    except (json.JSONDecodeError, KeyError, TypeError):
        return [f"{TASKS_FILE}: cannot read it before and after the change"]
    violations = []
    for task_id, task in before.items():
        kept = after.get(task_id, {})
        for mark in TASK_MARKS:
            if task.get(mark) != kept.get(mark):
                violations.append(f"{TASKS_FILE}: {task_id} changes its {mark} mark")
        kept_checks = kept.get("checks", [])
        if any("confirm" in c and c not in kept_checks for c in task.get("checks", [])):
            violations.append(f"{TASKS_FILE}: {task_id} drops a confirm check")
    for task_id in after.keys() - before.keys():
        if after[task_id].get("held_out"):
            violations.append(f"{TASKS_FILE}: {task_id} is added as held out")
    return violations
