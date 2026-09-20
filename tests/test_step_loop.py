"""The Jev step loop's failure handling and its one-call-per-step invariant (AGENTS.md §5, D37).

A silent bug here presses the wrong control, presses the same wrong control forever, or hangs
the voice loop when Jev is unreachable — all three hurt the user directly.
"""

from __future__ import annotations

import threading

import pytest

from zoya import decisions
from zoya.agents import step_loop
from zoya.config import COMPUTER_MAX_JEV_STEPS, COMPUTER_TRANSIENT_RETRIES
from zoya.tools import ToolError


def answers(control="c0", confidence=1.0, done=0.0, worked=1.0, failure="transient", risky=0.0):
    return decisions.Answers(
        {
            "control": {"choice": control, "confidence": confidence, "probabilities": {}},
            "done": {"noul": done},
            "worked": {"noul": worked},
            "irreversible": {"noul": risky},
            "failure": {"choice": failure, "confidence": 1.0, "probabilities": {}},
        },
        latency_ms=600,
    )


@pytest.fixture
def screen(monkeypatch):
    """Two pressable controls, a recording ax_press, and a Jev whose replies the test supplies."""
    state = {"pressed": [], "asked": [], "replies": []}

    controls = [("AXButton", "Appearance", object()), ("AXButton", "Dark", object())]
    monkeypatch.setattr(step_loop.ax, "front_app", lambda: ("System Settings", object()))
    monkeypatch.setattr(step_loop.ax, "read_controls", lambda _app: (controls, False))
    monkeypatch.setattr(step_loop.tasks, "gui_checkpoint", lambda _lock: False)
    monkeypatch.setattr(step_loop.computer, "log_stage", lambda *a, **k: None)
    monkeypatch.setattr(step_loop.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        step_loop.ax, "ax_press", lambda label, occurrence=1: state["pressed"].append(label)
    )

    def ask(_state, questions, **_kwargs):
        state["asked"].append(set(questions))
        return state["replies"].pop(0) if state["replies"] else decisions.unavailable("empty")

    monkeypatch.setattr(step_loop.decisions, "ask", ask)
    step_loop.computer.begin_session()
    return state


def run(cancel=None):
    return step_loop.run("turn on dark mode", [], cancel or threading.Event())


def test_one_jev_call_per_step_carrying_every_question(screen):
    screen["replies"] = [answers(control="c1"), answers(done=1.0)]
    outcome = run()
    assert outcome.done and not outcome.escalate
    assert outcome.steps == 1
    assert outcome.jev_calls == 2
    assert len(screen["asked"]) == 2
    assert screen["asked"][0] == {"control", "worked", "irreversible", "done", "failure"}
    assert screen["pressed"] == ["Dark"]


def test_jev_unavailable_escalates_and_never_raises(screen):
    screen["replies"] = [decisions.unavailable("timed out")]
    outcome = run()
    assert outcome.escalate and not outcome.done
    assert outcome.reason == "timed out"
    assert screen["pressed"] == []


def test_dead_end_gives_up_instead_of_counting_to_three(screen):
    screen["replies"] = [answers(), answers(worked=0.0, failure="dead_end")]
    outcome = run()
    assert outcome.escalate
    assert outcome.reason == step_loop.STALLED
    assert outcome.steps == 1


def test_wrong_element_stops_offering_that_control(screen):
    screen["replies"] = [
        answers(control="c0"),
        answers(control="c0", worked=0.0, failure="wrong_element"),
        answers(control="c1"),
        answers(done=1.0),
    ]
    outcome = run()
    assert outcome.done
    assert screen["pressed"] == ["Appearance", "Dark"]
    assert outcome.recorded == [
        {"tool": "ax_press", "args": {"label": "Appearance", "occurrence": 1}},
        {"tool": "ax_press", "args": {"label": "Dark", "occurrence": 1}},
    ]


def test_transient_retries_are_bounded(screen):
    screen["replies"] = [answers()] + [answers(worked=0.0, failure="transient")] * 8
    outcome = run()
    assert outcome.escalate
    assert outcome.steps <= 1 + COMPUTER_TRANSIENT_RETRIES
    assert outcome.jev_calls <= COMPUTER_MAX_JEV_STEPS


def test_coming_back_to_a_screen_already_acted_from_gives_up(screen):
    screen["replies"] = [answers(control="c0")] * COMPUTER_MAX_JEV_STEPS
    outcome = run()
    assert outcome.escalate and not outcome.done
    assert outcome.reason == step_loop.CIRCLING
    assert screen["pressed"] == ["Appearance"]
    assert outcome.jev_calls < COMPUTER_MAX_JEV_STEPS


def test_low_confidence_pick_is_not_acted_on(screen):
    screen["replies"] = [answers(confidence=0.5)]
    outcome = run()
    assert outcome.escalate
    assert screen["pressed"] == []


def test_a_failed_press_is_not_recorded_as_a_flow_step(screen, monkeypatch):
    def refuse(label, occurrence=1):
        raise ToolError("I can't find that.")

    monkeypatch.setattr(step_loop.ax, "ax_press", refuse)
    screen["replies"] = [answers(), answers(done=1.0)]
    outcome = run()
    assert outcome.recorded == []


def test_irreversible_only_ever_adds_a_confirmation(screen):
    screen["replies"] = [answers(risky=1.0), answers(done=1.0)]
    outcome = run()
    assert outcome.done
    assert step_loop.computer.session.asked is True
    assert outcome.recorded, "the press still happened; Jev may raise the bar, never lower it"


def test_cancellation_stops_before_any_press(screen):
    screen["replies"] = [answers()]
    cancel = threading.Event()
    cancel.set()
    outcome = run(cancel)
    assert outcome.escalate and screen["pressed"] == []


def test_triage_fails_closed_when_jev_is_unsure():
    unsure = decisions.Answers(
        {"failure": {"choice": "transient", "confidence": 0.4, "probabilities": {}}}
    )
    assert step_loop.triage(unsure) == "dead_end"
    assert step_loop.triage(decisions.Answers({})) == "dead_end"


@pytest.mark.parametrize(
    ("name", "count", "expected"),
    [("c0", 2, 0), ("c1", 2, 1), ("c2", 2, None), ("none_of_these", 2, None), ("cx", 2, None)],
)
def test_control_key_parser(name, count, expected):
    assert step_loop.index_of(name, count) == expected


def test_occurrence_counts_controls_sharing_a_name():
    controls = [("AXButton", "Open", None), ("AXButton", "Close", None), ("AXButton", "Open", None)]
    assert step_loop.occurrence_of(controls, 0) == 1
    assert step_loop.occurrence_of(controls, 2) == 2


SNAPSHOT = """- searchbox "Search Amazon.in" [ref=e430]: wireless mouse
- button "Add to cart" [ref=e898]
- button [ref=e1214]
"""


def test_a_web_page_is_read_and_clicked_by_ref_never_by_its_macos_tree(screen, monkeypatch):
    """D84: a browser window's AX tree never reaches Jev; the snapshot substrate does."""
    from zoya.tools import browser

    clicked = []
    monkeypatch.setattr(step_loop.ax, "read_controls", lambda _app: ([], True))
    monkeypatch.setattr(browser, "snapshot", lambda: SNAPSHOT)
    monkeypatch.setattr(browser, "click_ref", lambda ref, name: clicked.append((ref, name)))
    screen["replies"] = [answers(control="e898"), answers(done=1.0)]

    outcome = run()

    assert outcome.done
    assert clicked == [("e898", 'button "Add to cart"')]
    assert outcome.recorded == [], "a ref is a handle, not an identity: never record it as a flow"
    assert step_loop.computer.session.asked is True


def test_unnamed_refs_are_not_offered_to_jev():
    keys = {c.key for c in step_loop.web_candidates(SNAPSHOT)}

    assert keys == {"e430", "e898"}


WRAPPED = """- generic "Add to cart" [ref=e826] clickable [cursor:pointer]
  - button "Add to cart" [ref=e898]
- button "Buy now" [ref=e900]
"""


def test_the_inner_ref_is_offered_not_the_clickable_wrapper():
    """Guard 2 reads its evidence by focusing the ref, and a wrapper is not focusable."""
    keys = {c.key for c in step_loop.web_candidates(WRAPPED)}

    assert keys == {"e898", "e900"}
