"""Why a task failed, and the record of it a cloud session may read.

`cause` reads only what `evals/harness/run.py` recorded. `record` keeps the evidence already in the
Run JSON but never a tool's input, a URL's query, an email other than the harness's own, or a run
of ten or more digits. A held-out task's record is its pass or fail only.
Standard library only; never imports zoya.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

TEXT_CHARS = 300
LAST_TOOLS = 5
HARNESS_EMAIL = "harness@example.com"
EMAIL_MASK = "[email]"
DIGITS_MASK = "[digits]"
TRUNCATED = "…"
TIMEOUT_PREFIX = "over "

PASSED = "pass"
TIMEOUT, CRASH, FALSE_ASK = "timeout", "crash", "false-ask"
NEVER_REACHED_GATE, ASK_WORDING, WALL = "never-reached-gate", "ask-wording", "wall"
WRONG_PAGE, WRONG_ANSWER = "wrong-page", "wrong-answer"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DIGITS = re.compile(r"\d{10,}")
_WALL = re.compile(r"\bsign(?:ing)?[ -]?in\b|\blog(?:ging)?[ -]?in\b|\bcaptcha\b", re.I)


def cause(task: Mapping[str, Any], run: Mapping[str, Any]) -> str:
    """One of the failure classes for a run, or "pass". `task` is its tasks.json entry."""
    if run["success"] is True:
        return PASSED
    error = run.get("error") or ""
    if error.startswith(TIMEOUT_PREFIX):
        return TIMEOUT
    if error:
        return CRASH
    said = " ".join(run.get("said") or [])
    asked = run.get("confirmations") or []
    failed = " ".join(run.get("failed_checks") or [])
    if task.get("stakes"):
        if not asked:
            return NEVER_REACHED_GATE
        if '"confirm"' in failed:
            return ASK_WORDING
    elif asked:
        return FALSE_ASK
    if _WALL.search(said):
        return WALL
    if '"url"' in failed:
        return WRONG_PAGE
    return WRONG_ANSWER


def redact(text: str) -> str:
    """Emails other than the harness's own and runs of ten or more digits, masked."""
    text = _EMAIL.sub(_mask_email, text)
    return _DIGITS.sub(DIGITS_MASK, text)


def record(
    task: Mapping[str, Any], run: Mapping[str, Any], klass: str, history: list[bool]
) -> dict[str, Any]:
    """What a day session reads about one failing task: its class, pass history, cause and the
    run's evidence, redacted."""
    return {
        "task": run["id"],
        "group": run["group"],
        "class": klass,
        "history": "".join("P" if ok else "F" for ok in history),
        "cause": cause(task, run),
        "failed_checks": [redact(check) for check in run.get("failed_checks") or []],
        "said": _tail(" | ".join(run.get("said") or [])),
        "confirmations": [_tail(text) for text in run.get("confirmations") or []],
        "tools": [_tool_name(tool) for tool in (run.get("tools") or [])[-LAST_TOOLS:]],
        "url": _tail(strip_query(run.get("url") or "")),
        "error": _tail(run.get("error") or ""),
    }


def held_out_record(task_id: str, success: bool) -> dict[str, Any]:
    return {"task": task_id, "held_out": True, "result": PASSED if success else "fail"}


def strip_query(url: str) -> str:
    """The URL without its query, fragment or user info."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        netloc = f"{host}:{parts.port}" if parts.port else host
    except ValueError:
        netloc = host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _mask_email(match: re.Match[str]) -> str:
    return match.group(0) if match.group(0).casefold() == HARNESS_EMAIL else EMAIL_MASK


def _tail(text: str) -> str:
    """Redacted first, so no email or digit run is cut in half, then the last TEXT_CHARS."""
    text = redact(text)
    return text if len(text) <= TEXT_CHARS else TRUNCATED + text[-(TEXT_CHARS - 1) :]


def _tool_name(tool: object) -> str:
    """run.py records a tool as its name, a space, then its JSON input; only the name is kept."""
    return redact((str(tool).split(maxsplit=1) or [""])[0])
