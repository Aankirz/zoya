"""A2: a slow skill action hands over to the brain within 8 s, and never asks after it is dropped."""

import threading
import time

import pytest

from zoya import config, harness, orchestrator, safety
from zoya.router import RouteDecision
from zoya.tools import ToolError, check_abandoned

FALLBACK_BUDGET_S = 8.0
BRAIN_FIRST_WORD_S = 1.5
SHORT_DEADLINE_S = 0.3


@pytest.fixture
def short_deadline(monkeypatch):
    monkeypatch.setattr(orchestrator, "SKILL_ACTION_DEADLINE_S", SHORT_DEADLINE_S)
    monkeypatch.setattr(harness, "action_tools", lambda: {"slow_post": object()})


def test_the_deadline_leaves_room_for_the_brain_inside_eight_seconds():
    assert config.SKILL_ACTION_DEADLINE_S + BRAIN_FIRST_WORD_S <= FALLBACK_BUDGET_S


def test_a_hanging_action_falls_back_to_the_brain_at_the_deadline(monkeypatch, short_deadline):
    after_abandon: list[str] = []

    def hangs(_action, _args):
        time.sleep(SHORT_DEADLINE_S * 3)
        try:
            check_abandoned()
        except ToolError as refused:
            after_abandon.append(str(refused))
        return "posted"

    monkeypatch.setattr(harness, "run_action", hangs)
    monkeypatch.setattr(orchestrator, "run_orchestrator", lambda text, timings, skill: "brain")
    decision = RouteDecision("skill", "slow_post", {"text": "hi"}, text="post hi", skill="x")
    timings: dict[str, int] = {}

    started = time.monotonic()
    assert orchestrator.run_skill(decision, timings) == "brain"
    assert time.monotonic() - started < SHORT_DEADLINE_S * 2
    assert timings[orchestrator.SKILL_DEADLINE] == 1
    time.sleep(SHORT_DEADLINE_S * 3)
    assert after_abandon == ["That step ran out of time, so I stopped it."]


def test_an_action_waiting_on_the_users_confirmation_is_not_cut_off(monkeypatch, short_deadline):
    asking = threading.Event()

    def asks(_action, _args):
        asking.set()
        time.sleep(SHORT_DEADLINE_S * 3)
        return "Posted."

    monkeypatch.setattr(harness, "run_action", asks)
    monkeypatch.setattr(safety, "pending_task_id", lambda: "me" if asking.is_set() else None)
    monkeypatch.setattr(safety, "current_task_id", lambda: "me")
    decision = RouteDecision("skill", "slow_post", {"text": "hi"}, text="post hi", skill="x")

    assert orchestrator.run_skill(decision, {}) == "Posted."
