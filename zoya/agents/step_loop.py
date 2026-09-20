"""The Jev step loop (§9.5, D81, D82): one screen read plus one batched Jev call per step.

`computer_agent` runs this first and falls back to its language-model agent when Jev cannot
answer or cannot make progress. Every action still goes through the same guarded tool
functions, so Guard 2, the confirmation gate and the recorded-flow steps are unchanged.

Jev can only add a confirmation, never remove one: its `irreversible` answer raises the bar,
and the tools' own Guard 2 decides what actually needs the user's voice.

Two substrates, no crossover (D84): a native window is read through the accessibility tree
and pressed with `ax_press`; a browser window is read through agent-browser's snapshot and
clicked by ref, because one Safari article's AX tree is 24k tokens. A ref is a handle and not
an identity, so web steps are never recorded as a replayable flow.

API: https://docs.typesafe.ai/introduction/quickstart (state + batched questions).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from typesafe_sdk import Choice, Noul

from zoya import decisions, safety, tasks
from zoya.config import (
    COMPUTER_MAX_JEV_STEPS,
    COMPUTER_TRANSIENT_RETRIES,
    JEV_STEP_CONFIDENCE,
    JEV_STEP_NOUL,
    MAX_FAILED_ATTEMPTS,
)
from zoya.tools import ToolError, ax, computer

NONE_OF_THESE = "none_of_these"
CONTROL_PREFIX = "c"

PICK_QUESTION = (
    "Which listed control should the assistant press next to get closer to the goal? "
    "Choose none_of_these when no listed control moves the goal forward."
)
WORKED_QUESTION = (
    "Did the assistant's previous action do what it intended, judging by the screen now?"
)
IRREVERSIBLE_QUESTION = (
    "Would pressing the control that best serves the goal do something that cannot be undone, "
    "such as paying, ordering, sending, posting, deleting or quitting?"
)
DONE_QUESTION = "Has the goal already been achieved on the screen described here?"
TRIAGE_QUESTION = "Why did the assistant's previous action not work?"
TRIAGE_KINDS = {
    "transient": "the screen was still loading or animating, so the same action would work now",
    "wrong_element": "the control that was pressed was the wrong one for this goal",
    "dead_end": "this screen cannot reach the goal at all; a different approach is needed",
}
NONE_OF_THESE_CRITERION = "no control listed here moves the goal forward"

STATE_TEMPLATE = """\
A voice assistant is operating the Mac app {app!r} for a blind user.

Goal: {goal}
{plan}Previous action: {last}

The controls the app publishes right now, one per line:
{controls}"""
NO_PLAN = ""
PLAN_TEMPLATE = "Steps a planner suggested: {steps}\n"
NOTHING_YET = "none yet, this is the first step"

STALLED = "I couldn't find a way to do that in this app."
NO_CONTROLS = "that app doesn't publish any controls to press."
JEV_DOWN = "jev unavailable"
PRESSED = "pressed "
BUSY_SCREEN = "the screen stayed busy with another task."


@dataclass
class Outcome:
    """What the Jev loop achieved. `escalate` means the language-model agent should take over."""

    done: bool = False
    escalate: bool = True
    reason: str = ""
    steps: int = 0
    jev_calls: int = 0
    jev_ms: int = 0
    pressed: list[str] = field(default_factory=list)
    recorded: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    """One control Jev may pick, and how to act on it through a guarded tool."""

    key: str
    label: str
    press: Any
    record: dict[str, Any] | None = None


def control_key(index: int) -> str:
    return f"{CONTROL_PREFIX}{index}"


def pressable(items: list[tuple[str, str, Any]]) -> list[tuple[str, str, Any]]:
    return [(role, name, element) for role, name, element in items if role in ax.PRESSABLE_ROLES]


def native_candidates(items: list[tuple[str, str, Any]]) -> list[Candidate]:
    """Pressable accessibility controls, each pressed by the name `ax_read` listed."""
    controls = pressable(items)
    made = []
    for index, (role, name, _element) in enumerate(controls):
        args = {"label": name, "occurrence": occurrence_of(controls, index)}
        made.append(
            Candidate(
                key=control_key(index),
                label=ax.listed_line(role, name),
                press=lambda a=args: ax.ax_press(**a),
                record={"tool": "ax_press", "args": args},
            )
        )
    return made


def innermost(nodes: list[Any]) -> list[Any]:
    """Drop a clickable wrapper when a later ref carries the same accessible name.

    Guard 2 reads its evidence by focusing the ref, and a wrapper like
    `generic "Add to cart" [ref=e826]` around `button "Add to cart" [ref=e898]` is not focusable,
    so focus lands on the body and the submit and control-name signals read empty. Offering the
    inner ref keeps the guard at full strength.
    """
    wrapped = {
        node.name
        for index, node in enumerate(nodes)
        if node.clickable
        for later in nodes[index + 1 :]
        if later.name == node.name
    }
    return [node for node in nodes if not (node.clickable and node.name in wrapped)]


def web_candidates(snapshot_text: str) -> list[Candidate]:
    """Snapshot refs, clicked through `click_ref` so Guard 2 re-verifies the ref before acting."""
    from zoya.tools import browser

    named = [node for node in browser.parse_refs(snapshot_text).values() if node.name]
    made = []
    for node in innermost(named):
        identity = node.identity()
        made.append(
            Candidate(
                key=node.ref,
                label=identity,
                press=lambda r=node.ref, seen=identity: browser.click_ref(r, seen),
            )
        )
    return made


def occurrence_of(controls: list[tuple[str, str, Any]], index: int) -> int:
    """Which control with this name it is, so `ax_press` presses the same one Jev picked."""
    name = safety.normalise(controls[index][1])
    return sum(1 for role, other, _e in controls[: index + 1] if safety.normalise(other) == name)


def criteria_of(candidates: list[Candidate]) -> dict[str, str]:
    criteria = {candidate.key: candidate.label for candidate in candidates}
    return {**criteria, NONE_OF_THESE: NONE_OF_THESE_CRITERION}


def step_state(app: str, goal: str, plan: list[str], last: str, controls: list[str]) -> str:
    return STATE_TEMPLATE.format(
        app=app,
        goal=goal,
        plan=PLAN_TEMPLATE.format(steps="; ".join(plan)) if plan else NO_PLAN,
        last=last or NOTHING_YET,
        controls="\n".join(controls),
    )


def step_questions(criteria: dict[str, str]) -> dict[str, Any]:
    """Every question one step needs, in one request (D82). Ten questions cost what one costs."""
    return {
        "control": Choice(instructions=PICK_QUESTION, criteria=criteria),
        "worked": Noul(instructions=WORKED_QUESTION),
        "irreversible": Noul(instructions=IRREVERSIBLE_QUESTION),
        "done": Noul(instructions=DONE_QUESTION),
        "failure": Choice(instructions=TRIAGE_QUESTION, criteria=TRIAGE_KINDS),
    }


def index_of(pick_name: str, count: int) -> int | None:
    if not pick_name.startswith(CONTROL_PREFIX):
        return None
    try:
        index = int(pick_name[len(CONTROL_PREFIX) :])
    except ValueError:
        return None
    return index if 0 <= index < count else None


def chosen(candidates: list[Candidate], pick_name: str) -> Candidate | None:
    """The candidate Jev named. `none_of_these` and anything unrecognised resolve to None."""
    return next((c for c in candidates if c.key == pick_name), None)


def triage(answers: decisions.Answers) -> str:
    """The failure kind Jev named, or dead_end when it could not name one (fail closed)."""
    pick = answers.pick("failure")
    if pick is None or pick.confidence < JEV_STEP_CONFIDENCE:
        return "dead_end"
    return pick.name


@dataclass
class _Progress:
    last: str = ""
    wrong: set[str] = field(default_factory=set)
    transient: int = 0
    relook: bool = False


def run(goal: str, plan: list[str], cancel: Any) -> Outcome:
    """Drive the frontmost app toward `goal` with exactly one Jev call per step."""
    outcome, progress = Outcome(), _Progress()
    for _step in range(COMPUTER_MAX_JEV_STEPS):
        if cancel.is_set() or computer.session.stop_reason:
            return _stop(outcome, computer.session.stop_reason or "cancelled")
        if (handover := _gui_checkpoint()) is not None:
            return _stop(outcome, handover)
        app, candidates = _look()
        offered = [c for c in candidates if c.label not in progress.wrong]
        if not offered:
            return _stop(outcome, NO_CONTROLS)
        answers = _ask(outcome, app, goal, plan, progress.last, offered)
        if not answers:
            return _stop(outcome, answers.reason or JEV_DOWN)
        if answers.noul("done") >= JEV_STEP_NOUL:
            outcome.done, outcome.escalate = True, False
            return outcome
        if not _triaged(answers, progress, outcome):
            return _stop(outcome, STALLED)
        if progress.relook:
            continue
        stopped = _act(answers, offered, progress, outcome)
        if stopped:
            return _stop(outcome, stopped)
    return _stop(outcome, STALLED)


def _gui_checkpoint() -> str | None:
    """§9.13: yield the screen to a user command started meanwhile, then look again."""
    try:
        resumed = tasks.gui_checkpoint(computer.gui_lock)
    except TimeoutError:
        computer.session.stop_reason = BUSY_SCREEN
        return BUSY_SCREEN
    if resumed:
        computer.begin_session()
        computer.session.asked = True
    return None


def _look() -> tuple[str, list[Candidate]]:
    """The frontmost window on its own substrate: accessibility for native, refs for web (D84)."""
    from zoya.tools import browser

    app, element = ax.front_app()
    items, web = ax.read_controls(element)
    if not web:
        return app, native_candidates(items)
    return app, web_candidates(browser.snapshot())


def _triaged(answers: decisions.Answers, progress: _Progress, outcome: Outcome) -> bool:
    """Failure triage (D81) in place of counting to three. False means give up honestly."""
    progress.relook = False
    if not progress.last or answers.noul("worked") >= JEV_STEP_NOUL:
        progress.transient = 0
        return True
    kind = triage(answers)
    computer.log_stage("computer_step_triage", kind=kind, step=outcome.steps)
    if kind == "dead_end":
        return False
    if kind == "transient" and progress.transient < COMPUTER_TRANSIENT_RETRIES:
        progress.transient += 1
        progress.relook = True
        time.sleep(computer.ACTION_SETTLE_S)
        return True
    progress.transient = 0
    if kind == "wrong_element" and progress.last.startswith(PRESSED):
        progress.wrong.add(progress.last.removeprefix(PRESSED))
        progress.relook = True
    return True


def _act(
    answers: decisions.Answers,
    candidates: list[Candidate],
    progress: _Progress,
    outcome: Outcome,
) -> str:
    """Act on what Jev picked. Returns "" to continue, or the reason the loop must stop."""
    pick = answers.pick("control")
    candidate = chosen(candidates, pick.name) if pick else None
    if candidate is None or pick.confidence < JEV_STEP_CONFIDENCE:
        return STALLED
    if answers.noul("irreversible") >= JEV_STEP_NOUL:
        computer.session.asked = True
    progress.last = _press(candidate, progress, outcome)
    outcome.steps += 1
    if computer.session.failures >= MAX_FAILED_ATTEMPTS:
        return computer.session.stop_reason or STALLED
    return ""


def _ask(
    outcome: Outcome,
    app: str,
    goal: str,
    plan: list[str],
    last: str,
    candidates: list[Candidate],
) -> decisions.Answers:
    criteria = criteria_of(candidates)
    state = step_state(app, goal, plan, last, [c.label for c in candidates])
    answers = decisions.ask(state, step_questions(criteria))
    outcome.jev_calls += 1
    outcome.jev_ms += answers.latency_ms
    computer.log_stage(
        "computer_step_jev", jev_ms=answers.latency_ms, controls=len(candidates), ok=bool(answers)
    )
    return answers


def _press(candidate: Candidate, progress: _Progress, outcome: Outcome) -> str:
    """Through the guarded tool, so Guard 2, the blocked-target refusal and the gate all run."""
    try:
        candidate.press()
    except ToolError as error:
        progress.wrong.add(candidate.label)
        return f"tried {candidate.label} and it failed: {error}"
    outcome.pressed.append(candidate.label)
    if candidate.record is None:
        computer.session.asked = True
    else:
        outcome.recorded.append(candidate.record)
    return PRESSED + candidate.label


def _stop(outcome: Outcome, reason: str) -> Outcome:
    outcome.done, outcome.escalate, outcome.reason = False, True, reason
    return outcome
