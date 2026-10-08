"""A5: a useful first line at once, step names while working, never ten seconds of silence."""

import time

import pytest

from zoya import config, orchestrator, progress, tasks

POLL_S = 0.02
SILENCE_S = 0.2
FIRST_S = 0.05


@pytest.mark.parametrize(
    ("command", "line"),
    [
        ("search for ferry times to Alibaug", "Looking up ferry times to Alibaug."),
        ("buy a pair of running socks", "Looking for a pair of running socks."),
        ("remind me to renew my passport next week", "Setting a reminder to renew your passport"),
        ("play the new Coldplay album", "Finding the new Coldplay album."),
    ],
)
def test_the_first_line_says_what_was_understood(command, line):
    assert progress.early_line(command).startswith(line)


@pytest.mark.parametrize("command", ["what time does the pharmacy close?", "hmm", "thanks"])
def test_questions_and_fragments_get_no_canned_first_line(command):
    assert progress.early_line(command) == ""


def test_a_question_is_answered_without_planning_effort():
    assert orchestrator.reasoning_effort("how far is the moon?") == "none"
    effort = orchestrator.reasoning_effort("find me a quiet cafe and book a table")
    assert effort == config.BRAIN_PLANNING_REASONING_EFFORT


@pytest.fixture
def fast_heartbeat(monkeypatch):
    said: list[tuple[float, str]] = []
    monkeypatch.setattr(progress, "PROGRESS_POLL_S", POLL_S)
    monkeypatch.setattr(progress, "PROGRESS_SILENCE_S", SILENCE_S)
    monkeypatch.setattr(progress, "FIRST_STEP_LINE_S", FIRST_S)
    monkeypatch.setattr(progress.speech, "is_speaking", lambda: False)

    def say(text, task=None):
        said.append((time.monotonic(), text))
        task.last_said_at = time.monotonic()

    monkeypatch.setattr(progress.tasks, "say", say)
    return said


def test_a_long_quiet_task_names_its_steps_and_is_never_silent_long(fast_heartbeat):
    task = tasks.Task("t1", "research", "compare three laptops")
    started = time.monotonic()
    with progress.heartbeat(task):
        task.step = "using web_search"
        time.sleep(SILENCE_S * 4)
    times = [started, *(at for at, _text in fast_heartbeat)]
    assert fast_heartbeat[0][1] == "Searching the web."
    assert max(b - a for a, b in zip(times, times[1:], strict=False)) < SILENCE_S * 2


def test_no_progress_line_while_a_confirmation_waits(fast_heartbeat):
    task = tasks.Task("t2", "order", "order a kettle")
    task.status = "waiting_confirmation"
    with progress.heartbeat(task):
        task.step = "using browser_click"
        time.sleep(SILENCE_S * 3)
    assert fast_heartbeat == []
