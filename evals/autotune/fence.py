"""The fence: may the night run a candidate branch unattended in the owner's Chrome? (v2)

    git diff --no-ext-diff --no-textconv origin/main...SHA | python -m evals.autotune.fence

`check(diff)` returns every reason the candidate may not run unattended; empty means it may.
It fails closed: anything it cannot account for is a reason. It is a tripwire and a scope limit,
not a sandbox: the owner still pins the reviewed commit before a night runs it.

- Only zoya/ may change, never zoya/safety.py, and no file there is deleted, renamed, re-moded
  or binary.
- tests/ may only gain new test_*.py files or new fixtures; existing tests and conftest.py are
  read-only, so a candidate can never weaken the suite that judges it.
- No added or removed line in zoya/ holds a protected word: surface.PROTECTED_WORDS plus the
  names of the caps and thresholds (JEV_STEP_CONFIDENCE, PER_TASK_COST_CAP_USD, the budgets).
- At most MAX_CHANGED_LINES changed lines, so the morning review stays a real review.

Standard library only; never imports zoya.
"""

from __future__ import annotations

import sys

from evals.autotune.surface import is_protected

MAX_CHANGED_LINES = 400
FORBIDDEN_FILES = ("zoya/safety.py",)
FENCE_WORDS = ("guard", "budget", "cost_cap", "confidence")
_NO_NEWLINE = "\\ No newline at end of file"
_FORBIDDEN_HEADERS = {
    "deleted file mode": "deletes a file",
    "old mode": "changes a file mode",
    "new mode": "changes a file mode",
    "similarity index": "renames or copies a file",
    "dissimilarity index": "rewrites a file",
    "rename from": "renames a file",
    "rename to": "renames a file",
    "copy from": "copies a file",
    "copy to": "copies a file",
    "GIT binary patch": "is a binary patch",
    "Binary files": "is a binary patch",
}


def is_fenced(line: str) -> bool:
    """True when a changed zoya/ line holds a word the night may not touch unattended."""
    folded = line.casefold()
    return is_protected(line) or any(word in folded for word in FENCE_WORDS)


def check(diff: str) -> list[str]:
    """Every reason this `git diff` may not run unattended; an empty list means it may."""
    if "\0" in diff or "\r" in diff:
        return ["the diff contains NUL bytes or carriage returns"]
    lines = diff.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return ["the diff is empty"]
    violations: list[str] = []
    path = ""
    new_file = in_hunk = False
    changed = 0
    for number, line in enumerate(lines, 1):
        if line.startswith("diff --git "):
            path, new_file, in_hunk = _header_path(line), False, False
            if not path:
                return [f"line {number}: cannot read the header {line!r}"]
            violations += _path_violations(path)
        elif not path:
            return [f"line {number}: expected 'diff --git', got {line!r}"]
        elif in_hunk and line[:1] in ("-", "+"):
            changed += 1
            if path.startswith("tests/") and not new_file:
                violations.append(f"{path}: an existing test file changes")
            elif path.startswith("zoya/") and is_fenced(line[1:]):
                verb = "removes or changes" if line[0] == "-" else "adds"
                violations.append(f"{path}: {verb} a fenced line: {line[1:].strip()!r}")
        elif in_hunk and (line[:1] == " " or line == _NO_NEWLINE):
            continue
        elif line.startswith("@@ "):
            in_hunk = True
        elif in_hunk:
            return [f"line {number}: unexpected line {line!r} in a hunk"]
        elif line.startswith("new file mode "):
            new_file = True
            if line != "new file mode 100644":
                violations.append(f"{path}: the diff adds a file that is not a plain file")
        elif reason := _forbidden_header(line):
            violations.append(f"{path}: the diff {reason}")
        elif line.startswith("+++ /dev/null"):
            violations.append(f"{path}: the diff deletes a file")
        elif not line.startswith(("index ", "--- ", "+++ ")):
            return [f"line {number}: unexpected header line {line!r}"]
    if changed > MAX_CHANGED_LINES:
        violations.append(f"{changed} changed lines; at most {MAX_CHANGED_LINES} run unattended")
    return list(dict.fromkeys(violations))


def _header_path(line: str) -> str:
    """The one path of `diff --git a/P b/P`, or "" when quoted, ambiguous or two paths."""
    parts = line[len("diff --git ") :].split(" ")
    if '"' in line or len(parts) != 2 or not parts[0].startswith("a/"):
        return ""
    old, new = parts[0][2:], parts[1][2:] if parts[1].startswith("b/") else ""
    return new if old == new and new and ".." not in new.split("/") else ""


def _path_violations(path: str) -> list[str]:
    if path in FORBIDDEN_FILES:
        return [f"{path}: the safety gate never changes unattended"]
    if path.startswith("zoya/"):
        return []
    if path.startswith("tests/") and not path.startswith(("tests/autotune/", "tests/evals/")):
        name = path.rsplit("/", 1)[-1]
        fixture_or_test = path.startswith("tests/fixtures/") or name.startswith("test_")
        if fixture_or_test and name != "conftest.py":
            return []
    return [f"{path}: only zoya/ and new tests may change"]


def _forbidden_header(line: str) -> str | None:
    for header, reason in _FORBIDDEN_HEADERS.items():
        if line.startswith(header):
            return reason
    return None


def main() -> int:
    violations = check(sys.stdin.read())
    for violation in violations:
        print(f"fence: {violation}", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
