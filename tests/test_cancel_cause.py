"""A1 (D159): "Okay, stopped." only when the user stopped, and every cancel names who set it."""

import json
import threading

import pytest

from zoya import orchestrator, speech, tasks
from zoya.router import RouteDecision

WAIT_S = 5.0


class CancellingAgent:
    """A brain whose run is cancelled by `cancel` while it streams, like Strands on a set flag."""

    messages: list = []
    event_loop_metrics = type("M", (), {"accumulated_usage": {}, "cycle_count": 1})()

    def __init__(self, cancel) -> None:
        self.cancel = cancel

    def __call__(self, command, cancel_signal):
        self.cancel(cancel_signal)
        return type("Result", (), {"stop_reason": "cancelled"})()


@pytest.fixture
def quiet(monkeypatch, tmp_path):
    said: list[str] = []
    monkeypatch.setattr(tasks, "TIMING_LOG", tmp_path / "timing.log", raising=False)
    monkeypatch.setattr(tasks, "LOG_DIR", tmp_path, raising=False)
    monkeypatch.setattr(speech, "narrate", said.append)
    monkeypatch.setattr(orchestrator, "_log_timing", lambda *_: None)
    monkeypatch.setattr(orchestrator.browser, "task_tabs", lambda: frozenset())
    monkeypatch.setattr(orchestrator.browser, "close_task_tabs", lambda _before: [])
    monkeypatch.setattr(orchestrator.speculate, "commit", lambda _text: None)
    monkeypatch.setattr(
        orchestrator, "route", lambda text: RouteDecision("orchestrator", text=text)
    )
    monkeypatch.setattr(orchestrator.events, "emit", lambda _event: None)
    tasks._reset_for_tests()
    yield said, tmp_path / "timing.log"
    orchestrator._conversation.clear()
    orchestrator._cancel.clear()


def _run_task(command: str) -> orchestrator.CommandResult:
    done: dict[str, orchestrator.CommandResult] = {}
    finished = threading.Event()

    def on_done(result):
        done["result"] = result
        finished.set()

    orchestrator.start_task(command, {}, on_done=on_done)
    assert finished.wait(WAIT_S)
    return done["result"]


def _cancel_records(log_path) -> list[dict]:
    lines = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    return [r for r in map(json.loads, lines) if r.get("event") == "cancel"]


def internal_cancel(signal) -> None:
    signal.set()


def test_a_cancel_the_user_never_asked_for_is_not_reported_as_stopped(monkeypatch, quiet):
    said, log_path = quiet
    monkeypatch.setattr(
        orchestrator, "build_orchestrator", lambda **_: CancellingAgent(internal_cancel)
    )

    result = _run_task("from Amazon.")

    assert result.spoken != orchestrator.STOPPED_MESSAGE
    assert not result.ok
    assert orchestrator.STOPPED_MESSAGE not in said
    assert said[-1] == result.spoken  # the failure is said out loud, not swallowed


def test_every_cancel_logs_who_set_it(monkeypatch, quiet):
    _said, log_path = quiet
    monkeypatch.setattr(
        orchestrator, "build_orchestrator", lambda **_: CancellingAgent(internal_cancel)
    )

    result = _run_task("Here's where")

    [record] = _cancel_records(log_path)
    assert record["task_id"] == result.task_id
    assert record["by_user"] is False
    assert record["source"].startswith("tests.test_cancel_cause.internal_cancel")


def test_a_user_stop_still_says_stopped_once(monkeypatch, quiet):
    said, log_path = quiet

    def user_stop(_signal):
        orchestrator.stop_task()

    monkeypatch.setattr(orchestrator, "build_orchestrator", lambda **_: CancellingAgent(user_stop))

    result = _run_task("tell me a long story")

    assert result.spoken == orchestrator.STOPPED_MESSAGE
    assert orchestrator.STOPPED_MESSAGE not in said  # the stop path speaks for itself
    [record] = _cancel_records(log_path)
    assert record["by_user"] is True
    assert any("orchestrator.stop_task" in frame for frame in record["chain"])


def test_an_idle_stop_is_attributed_to_the_user_and_cleared_by_the_next_command(quiet):
    orchestrator.stop_task()

    assert orchestrator._cancel.by_user
    orchestrator._cancel.clear()
    assert orchestrator._cancel.cause is None and not orchestrator._cancel.is_set()


def test_a_stop_jev_guessed_for_a_dispatched_command_goes_to_the_brain():
    guessed = RouteDecision("stop", source="jev", text="hmm, that was not what I meant")
    spoken = RouteDecision("stop", source="rules", text="stop")

    assert orchestrator.not_a_guessed_stop(guessed).route == "orchestrator"
    assert orchestrator.not_a_guessed_stop(spoken).route == "stop"
