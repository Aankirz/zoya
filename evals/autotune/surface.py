"""What the autotuner may change, and the gate every candidate patch passes before it runs.

`check_patch` reads a unified diff strictly and fails closed: anything it cannot account for is a
violation. It checks each changed line of the diff, then applies the diff in memory to the files
under `root` and compares the Python before and after, so a patch can only move an allowed
constant within its range or edit prompt text that no protected word sits in or next to.
Standard library only; never imports zoya.
"""

from __future__ import annotations

import ast
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = "zoya/config.py"
PROMPT_FILE = "zoya/prompts.py"
ALLOWED_FILES = (CONFIG_FILE, PROMPT_FILE)

# A tuple of strings is the allowed values; a numeric pair is an inclusive range whose bounds'
# type sets the value's type (int bounds take ints only, float bounds take ints or floats).
ALLOWED_CONSTANTS: dict[str, tuple] = {
    "BRAIN_PLANNING_REASONING_EFFORT": ("low", "medium", "high"),
    "BRAIN_STEP_REASONING_EFFORT": ("none", "low"),
    "COMPUTER_MAX_JEV_STEPS": (6, 20),
    "MAX_FAILED_ATTEMPTS": (2, 5),
    "WEB_RENDER_WAIT_S": (2.0, 10.0),
    "MAX_TOOL_CALLS_PER_TASK": (20, 60),
}

# Matched case-insensitively as substrings, so "Never", "confirms" and "payment" are protected.
PROTECTED_WORDS = (
    "confirm",
    "password",
    "otp",
    "card",
    "pay",
    "order",
    "purchase",
    "safety",
    "never",
    "stop",
    "secret",
    "store",
    "untrusted",
    "delete",
    "send",
    "post",
)

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$")
_INDEX = re.compile(r"^index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?$")
_NO_NEWLINE = "\\ No newline at end of file"
_FORBIDDEN_HEADERS = {
    "new file mode": "adds a new file",
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


@dataclass
class _Hunk:
    old_start: int
    new_start: int
    lines: list[tuple[str, str]] = field(default_factory=list)  # (" " | "-" | "+", text)


@dataclass
class _FilePatch:
    path: str
    hunks: list[_Hunk] = field(default_factory=list)


def check_patch(unified_diff: str, root: Path | str | None = None) -> list[str]:
    """Every reason the patch is not allowed; an empty list means it is.

    `root` is the checkout the patch applies to (default: the repository holding this module).
    The patch must apply there exactly, or it is rejected.
    """
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    patches, violations = _parse(unified_diff)
    if violations:
        return violations
    for patch in patches:
        if patch.path == CONFIG_FILE:
            violations += _check_config_lines(patch)
        else:
            violations += _check_prompt_lines(patch)
    if violations:
        return list(dict.fromkeys(violations))
    for patch in patches:
        violations += _check_applied(patch, root)
    return list(dict.fromkeys(violations))


def value_violation(name: str, value: object) -> str | None:
    """Why `value` is not allowed for constant `name`, or None when it is."""
    spec = ALLOWED_CONSTANTS.get(name)
    if spec is None:
        return f"{name} is not a constant the tuner may change"
    if all(isinstance(allowed, str) for allowed in spec):
        if isinstance(value, str) and value in spec:
            return None
        return f"{name} = {value!r} is not one of {', '.join(map(repr, spec))}"
    low, high = spec
    number_types = (int,) if isinstance(low, int) else (int, float)
    if isinstance(value, bool) or not isinstance(value, number_types):
        return f"{name} = {value!r} must be {'an int' if number_types == (int,) else 'a number'}"
    if not low <= value <= high:
        return f"{name} = {value!r} is outside {low}..{high}"
    return None


def is_protected(line: str) -> bool:
    """True when the line contains a protected word, ignoring case and invisible characters."""
    text = _normalize(line)
    return any(word in text for word in PROTECTED_WORDS)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf").casefold()


# --- Parsing -------------------------------------------------------------------------------------


def _parse(diff: str) -> tuple[list[_FilePatch], list[str]]:
    if "\0" in diff:
        return [], ["the patch contains NUL bytes (binary)"]
    if "\r" in diff:
        return [], ["the patch contains carriage returns"]
    lines = diff.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return [], ["the patch is empty"]
    patches: list[_FilePatch] = []
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        patch, i, error = _parse_file(lines, i)
        if error:
            return [], [error]
        if patch.path in seen:
            return [], [f"{patch.path} appears more than once in the patch"]
        seen.add(patch.path)
        patches.append(patch)
    return patches, []


def _parse_file(lines: list[str], i: int) -> tuple[_FilePatch, int, str | None]:
    empty = _FilePatch("")
    git_paths: tuple[str, str] | None = None
    if lines[i].startswith("diff --git "):
        git_paths = _split_git_header(lines[i])
        if git_paths is None:
            return empty, i, f"line {i + 1}: cannot read the header {lines[i]!r}"
        i += 1
        while i < len(lines) and not lines[i].startswith(("--- ", "diff --git ")):
            reason = _header_reason(lines[i])
            if reason:
                return empty, i, f"{git_paths[1]}: the patch {reason}"
            if not _INDEX.match(lines[i]):
                return empty, i, f"line {i + 1}: unexpected line {lines[i]!r}"
            i += 1
        if i >= len(lines) or not lines[i].startswith("--- "):
            return empty, i, f"{git_paths[1]}: the patch has no content changes (mode or binary)"
    elif not lines[i].startswith("--- "):
        reason = _header_reason(lines[i])
        if reason:
            return empty, i, f"line {i + 1}: the patch {reason}"
        return empty, i, f"line {i + 1}: expected a file header, got {lines[i]!r}"
    if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
        return empty, i, f"line {i + 1}: '---' is not followed by '+++'"
    old = _strip_prefix(lines[i][4:], "a/")
    new = _strip_prefix(lines[i + 1][4:], "b/")
    if old is None or new is None:
        if "/dev/null" in (lines[i][4:], lines[i + 1][4:]):
            return empty, i, f"line {i + 1}: the patch adds or deletes a file"
        return empty, i, f"line {i + 1}: file names must be a/<path> and b/<path>"
    if old != new:
        return empty, i, f"line {i + 1}: the patch renames {old} to {new}"
    if git_paths is not None and git_paths != (old, new):
        return empty, i, f"line {i + 1}: the file names disagree with the diff --git header"
    if new not in ALLOWED_FILES:
        return empty, i, f"{new}: only {' and '.join(ALLOWED_FILES)} may change"
    patch = _FilePatch(new)
    i += 2
    while i < len(lines) and lines[i].startswith("@@"):
        hunk, i, error = _parse_hunk(lines, i, new)
        if error:
            return empty, i, error
        patch.hunks.append(hunk)
    if not patch.hunks:
        return empty, i, f"{new}: the patch has no hunks"
    if i < len(lines) and not lines[i].startswith(("diff --git ", "--- ")):
        return empty, i, f"line {i + 1}: unexpected line {lines[i]!r}"
    return patch, i, None


def _parse_hunk(lines: list[str], i: int, path: str) -> tuple[_Hunk, int, str | None]:
    match = _HUNK.match(lines[i])
    if not match:
        return _Hunk(0, 0), i, f"line {i + 1}: cannot read the hunk header {lines[i]!r}"
    old_start, old_count, new_start, new_count = (
        int(group) if group is not None else 1 for group in match.groups()
    )
    hunk = _Hunk(old_start, new_start)
    i += 1
    old_seen = new_seen = 0
    while old_seen < old_count or new_seen < new_count:
        if i >= len(lines):
            return hunk, i, f"{path}: a hunk ends early"
        line = lines[i]
        tag, text = line[:1], line[1:]
        if tag == " ":
            old_seen, new_seen = old_seen + 1, new_seen + 1
        elif tag == "-":
            old_seen += 1
        elif tag == "+":
            new_seen += 1
        elif line == _NO_NEWLINE:
            i += 1
            continue
        else:
            return hunk, i, f"line {i + 1}: unexpected line {line!r} inside a hunk"
        hunk.lines.append((tag, text))
        i += 1
    if old_seen != old_count or new_seen != new_count:
        return hunk, i, f"{path}: a hunk's line counts disagree with its header"
    while i < len(lines) and lines[i] == _NO_NEWLINE:
        i += 1
    return hunk, i, None


def _split_git_header(line: str) -> tuple[str, str] | None:
    rest = line[len("diff --git ") :]
    if '"' in rest:
        return None
    parts = rest.split(" ")
    if len(parts) != 2:
        return None
    old, new = _strip_prefix(parts[0], "a/"), _strip_prefix(parts[1], "b/")
    if old is None or new is None:
        return None
    return old, new


def _strip_prefix(name: str, prefix: str) -> str | None:
    name = name.split("\t", 1)[0]
    if not name.startswith(prefix) or '"' in name:
        return None
    return name[len(prefix) :]


def _header_reason(line: str) -> str | None:
    for header, reason in _FORBIDDEN_HEADERS.items():
        if line.startswith(header):
            return reason
    return None


# --- Line checks ---------------------------------------------------------------------------------


def _check_config_lines(patch: _FilePatch) -> list[str]:
    violations = []
    for hunk in patch.hunks:
        removed: list[str] = []
        added: list[str] = []
        for tag, text in hunk.lines:
            if tag == " ":
                continue
            name, value, error = _read_assignment(text)
            if error:
                violations.append(f"{CONFIG_FILE}: {error}: {tag}{text}")
                continue
            if tag == "-":
                removed.append(name)
            else:
                added.append(name)
                reason = value_violation(name, value)
                if reason:
                    violations.append(f"{CONFIG_FILE}: {reason}")
        if sorted(removed) != sorted(added):
            violations.append(
                f"{CONFIG_FILE}: a hunk must replace each constant it touches exactly once "
                f"(removes {sorted(removed)}, adds {sorted(added)})"
            )
    return violations


def _read_assignment(text: str) -> tuple[str, object, str | None]:
    """(name, value, None) for `NAME = <literal>` with NAME allowed, else an error."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "", None, "not an allowed constant's assignment"
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign):
        return "", None, "not an allowed constant's assignment"
    node = tree.body[0]
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return "", None, "not an allowed constant's assignment"
    name = node.targets[0].id
    if name not in ALLOWED_CONSTANTS:
        return name, None, f"{name} is not a constant the tuner may change"
    if not isinstance(node.value, ast.Constant):
        return name, None, f"{name} must be assigned a plain literal"
    return name, node.value.value, None


def _check_prompt_lines(patch: _FilePatch) -> list[str]:
    violations = []
    for hunk in patch.hunks:
        for tag, text in hunk.lines:
            if tag != " " and is_protected(text):
                verb = "removes or changes" if tag == "-" else "adds"
                violations.append(f"{PROMPT_FILE}: the patch {verb} a protected line: {text!r}")
    return violations


# --- Whole-file checks ---------------------------------------------------------------------------


def _check_applied(patch: _FilePatch, root: Path) -> list[str]:
    path = root / patch.path
    try:
        old_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{patch.path}: cannot read it under {root}: {exc}"]
    old_lines = old_text.split("\n")
    applied = _apply(patch, old_lines)
    if isinstance(applied, str):
        return [applied]
    new_lines, removed_at, added_at = applied
    new_text = "\n".join(new_lines)
    if patch.path == CONFIG_FILE:
        return _compare_config(old_text, new_text)
    violations = _compare_prompts(old_text, new_text)
    violations += _check_neighbours(old_lines, removed_at, "removes or changes")
    violations += _check_neighbours(new_lines, added_at, "adds")
    return violations


def _apply(patch: _FilePatch, old_lines: list[str]) -> tuple[list[str], set[int], set[int]] | str:
    """The patched lines and the 0-based positions removed (old) and added (new)."""
    new_lines: list[str] = []
    removed_at: set[int] = set()
    added_at: set[int] = set()
    cursor = 0
    for hunk in patch.hunks:
        old_count = sum(tag != "+" for tag, _ in hunk.lines)
        start = hunk.old_start - 1 if old_count else hunk.old_start
        if start < cursor:
            return f"{patch.path}: hunks overlap or are out of order"
        new_lines += old_lines[cursor:start]
        position = start
        for tag, text in hunk.lines:
            if tag in " -":
                if position >= len(old_lines) or old_lines[position] != text:
                    return f"{patch.path}: the patch does not apply at line {position + 1}"
                if tag == "-":
                    removed_at.add(position)
                else:
                    new_lines.append(text)
                position += 1
            else:
                added_at.add(len(new_lines))
                new_lines.append(text)
        cursor = position
    new_lines += old_lines[cursor:]
    return new_lines, removed_at, added_at


def _compare_config(old_text: str, new_text: str) -> list[str]:
    try:
        old_tree, new_tree = ast.parse(old_text), ast.parse(new_text)
    except SyntaxError as exc:
        return [f"{CONFIG_FILE}: does not parse after the patch: {exc}"]
    if len(old_tree.body) != len(new_tree.body):
        return [f"{CONFIG_FILE}: the patch adds or removes statements"]
    violations = []
    for old, new in zip(old_tree.body, new_tree.body, strict=True):
        if ast.dump(old) == ast.dump(new):
            continue
        name = _allowed_assign_name(old)
        if name is None or name != _allowed_assign_name(new):
            violations.append(f"{CONFIG_FILE}: the patch changes code at line {old.lineno}")
            continue
        reason = value_violation(name, new.value.value)
        if reason:
            violations.append(f"{CONFIG_FILE}: {reason}")
    return violations


def _allowed_assign_name(node: ast.stmt) -> str | None:
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in ALLOWED_CONSTANTS
        and isinstance(node.value, ast.Constant)
    ):
        return node.targets[0].id
    return None


def _compare_prompts(old_text: str, new_text: str) -> list[str]:
    try:
        old_tree, new_tree = ast.parse(old_text), ast.parse(new_text)
    except SyntaxError as exc:
        return [f"{PROMPT_FILE}: does not parse after the patch: {exc}"]
    if _without_strings(old_tree) != _without_strings(new_tree):
        return [f"{PROMPT_FILE}: the patch changes code, not only prompt text"]
    return []


def _without_strings(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.dump(tree)


def _check_neighbours(lines: list[str], changed: set[int], verb: str) -> list[str]:
    """Changed prompt lines may not touch a protected line, nor spell a protected word across
    a line break with their neighbour."""
    violations = []
    for index in sorted(changed):
        for neighbour in (index - 1, index + 1):
            if 0 <= neighbour < len(lines) and is_protected(lines[neighbour]):
                violations.append(
                    f"{PROMPT_FILE}: the patch {verb} a line next to a protected line: "
                    f"{lines[neighbour]!r}"
                )
        before = lines[index - 1] if index > 0 else ""
        after = lines[index + 1] if index + 1 < len(lines) else ""
        joined = (
            before.rstrip() + lines[index].lstrip(),
            lines[index].rstrip() + after.lstrip(),
        )
        if any(is_protected(text) for text in joined):
            violations.append(
                f"{PROMPT_FILE}: the patch {verb} a line that spells a protected word with its "
                f"neighbour: {lines[index]!r}"
            )
    return violations
