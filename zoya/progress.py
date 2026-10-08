"""What Zoya says while a task works (A5): a useful first line at once, then real progress.

The first line repeats what was asked ("Looking up train times to Pune."), so a mishearing is
caught in a second and the line is never the same filler twice. While the task runs, a heartbeat
names the step it is on whenever she has been quiet for PROGRESS_SILENCE_S, so there is never a
ten-second silence.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from zoya import speech, tasks
from zoya.config import (
    FIRST_STEP_LINE_S,
    PROGRESS_POLL_S,
    PROGRESS_SILENCE_S,
)
from zoya.router import QUESTION, clean_command

_I = re.IGNORECASE
ACK_MAX_WORDS = 8
STILL_WORKING = "Still working on it."
STEP_PREFIX = "using "
TEMPLATES = [
    (
        re.compile(r"^(?:search|google|look\s+up|look)\s+(?:for\s+|up\s+)?(?P<x>.+)$", _I),
        "Looking up {x}.",
    ),
    (re.compile(r"^(?:find|compare|research|check)\s+(?P<x>.+)$", _I), "Checking {x}."),
    (re.compile(r"^(?:buy|order|purchase|get\s+me)\s+(?P<x>.+)$", _I), "Looking for {x}."),
    (re.compile(r"^play\s+(?P<x>.+)$", _I), "Finding {x}."),
    (re.compile(r"^(?:post|tweet|publish)\b.+$", _I), "Getting that post ready."),
    (
        re.compile(r"^(?:send|text|message|whatsapp|imessage|e-?mail|mail)\b.+$", _I),
        "Getting that message ready.",
    ),
    (re.compile(r"^(?:set|start)\s+(?P<x>.*\b(?:timer|alarm|reminder)\b.*)$", _I), "Setting {x}."),
    (re.compile(r"^remind\s+me\s+(?P<x>.+)$", _I), "Setting a reminder {x}."),
    (re.compile(r"^(?:switch|turn|change)\s+(?P<x>.+)$", _I), "Changing that: {x}."),
    (re.compile(r"^(?:read|summari[sz]e)\s+(?P<x>.+)$", _I), "Reading {x}."),
    (re.compile(r"^(?:write|draft|make|create)\s+(?P<x>.+)$", _I), "Writing {x}."),
    (re.compile(r"^(?:book|reserve)\s+(?P<x>.+)$", _I), "Looking for {x}."),
]
YOURS = {"my": "your", "me": "you", "i": "you", "i'm": "you're", "mine": "yours", "myself": "you"}


def early_line(command: str) -> str:
    """The first thing said for a command that will take a while, or "" when none fits."""
    text = clean_command(command)
    if not text or QUESTION.match(text):
        return ""
    for pattern, line in TEMPLATES:
        if match := pattern.match(text):
            what = match.groupdict().get("x") or ""
            return line.format(x=_yours(what)) if what else line
    return ""


def _yours(phrase: str) -> str:
    words = [YOURS.get(word.lower(), word) for word in phrase.strip(" .!?").split()]
    return " ".join(words[:ACK_MAX_WORDS])


def step_line(step: str) -> str:
    """ "using web_search" → "Searching the web." from the overlay's labels."""
    from zoya.overlay import TOOL_VERBS

    tool = step.removeprefix(STEP_PREFIX).replace("_", " ").strip()
    if not tool or tool == "starting":
        return ""
    label = TOOL_VERBS.get(tool, tool[:1].upper() + tool[1:])
    return f"{label}."


@contextmanager
def heartbeat(task: tasks.Task | None) -> Iterator[None]:
    """While the block runs: name the step after FIRST_STEP_LINE_S if nothing was said yet, and
    after every PROGRESS_SILENCE_S of quiet."""
    if task is None:
        yield
        return
    done = threading.Event()
    thread = threading.Thread(target=_beat, args=(task, done), name="zoya-progress", daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()


def _beat(task: tasks.Task, done: threading.Event) -> None:
    started, last_step = time.monotonic(), ""
    while not done.wait(PROGRESS_POLL_S):
        if task.cancel.is_set() or task.status != "running":
            continue
        if speech.is_speaking():
            task.last_said_at = time.monotonic()
            continue
        quiet = time.monotonic() - (task.last_said_at or started)
        first = task.last_said_at is None and time.monotonic() - started >= FIRST_STEP_LINE_S
        if not first and quiet < PROGRESS_SILENCE_S:
            continue
        line = step_line(task.step) if task.step != last_step else ""
        if first and not line:
            continue
        last_step = task.step
        tasks.say(line or STILL_WORKING, task)
