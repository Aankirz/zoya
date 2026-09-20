"""computer_agent (§9.5, §9.6): a Strands Agent that operates Mac apps, exposed to the brain as one
tool, `computer_task(goal)`.

Harness, cheapest first (docs/research/harness.md): replay a recorded flow (0 model calls) →
the user's Shortcuts → AX (T1) → pixels (T3). Strands provides the agent loop, hooks, the
sequential executor and cancellation; Zoya adds the GUI lock, screenshot pruning, the give-up
rule, recorded flows and the gate.

- One GUI task at a time (`computer.gui_lock`); "Zoya, stop" cancels it (its task's cancel signal).
- Phase 6 (§9.13): a user command started meanwhile pauses it at its next step (`GuiPause`): the
  lock is handed over, and on resume the planned step is dropped so the agent looks again.
- The safety gate is registered last, as on the orchestrator (safety.ConfirmationGate); every
  input tool also runs Guard 2 on its real target itself.
- Only the last KEEP_SCREENSHOTS screenshots stay in context (§9.3).
- Three failed attempts in a row, or the user moving the mouse, end the task honestly.
- Its cost counts against what is left of the task's cap.
- Recorded flows: a task that succeeded without any confirmation is stored as its input steps
  (open_app, ax_press, click with the AX labels it hit, key, scroll), keyed by intent + front
  app, in the style of Phase 4's learned picks (JSON under logs/, 7-day TTL). Next time it
  replays at 0 model calls through the SAME tool functions, so Guard 2 runs on every step; any
  mismatch (labels, screen size, app, no visible change, a refusal) falls back to the agent,
  which records again.

Strands 1.55.1 source: tools/decorator.py (`context=True` → ToolContext.agent),
hooks/events.py (BeforeModelCallEvent, AfterToolCallEvent), agent/agent.py (`cancel_signal`).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from strands import Agent, ToolContext, tool
from strands.hooks import (
    AfterToolCallEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)
from strands.tools.executors import SequentialToolExecutor
from strands.types.exceptions import EventLoopException

from zoya import safety, screen, tasks
from zoya.agents import step_loop
from zoya.config import (
    COMPUTER_FLOW_TTL_S,
    COMPUTER_FLOWS_FILE,
    GUI_PAUSE_MAX_S,
    KEEP_SCREENSHOTS,
    LOG_DIR,
    PER_TASK_COST_CAP_USD,
)
from zoya.prompts import COMPUTER_PROMPT
from zoya.tools import ToolError, ax, computer

BUSY = "I'm already using the screen for another task."
RESUMED = (
    "Paused while the user used the Mac; this step was not done. The screen may have changed: "
    "take a new screenshot before acting."
)
LOCK_POLL_S = 0.2
PRUNED_SCREENSHOT = {"text": "[older screenshot removed]"}
REPLAYED = "Done, the same way as last time."
MS_PER_S = 1000
SPENT_KEY = "computer_spent_usd"  # on the brain agent's state: earlier computer_task calls


class ComputerStopped(Exception):
    """Raised before a model call once the task must end (gave up, or the user took over)."""


class ScreenshotPruner(HookProvider):
    """Before each model call, drop all but the newest screenshots from the agent's messages."""

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self.prune)

    def prune(self, event: BeforeModelCallEvent) -> None:
        prune_screenshots(event.agent.messages, KEEP_SCREENSHOTS)


def prune_screenshots(messages: list[Any], keep: int) -> None:
    """Images live in toolResult content (Strands message format); replace older ones in place."""
    spots = []
    for message in messages:
        for block in message.get("content", []):
            content = block.get("toolResult", {}).get("content", [])
            spots += [(content, i) for i, item in enumerate(content) if "image" in item]
    for content, index in spots[: max(0, len(spots) - keep)]:
        content[index] = dict(PRUNED_SCREENSHOT)


class GiveUp(HookProvider):
    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self.check)

    def check(self, _event: BeforeModelCallEvent) -> None:
        if computer.session.stop_reason:
            raise ComputerStopped(computer.session.stop_reason)


class GuiPause(HookProvider):
    """§9.13 "the user always wins the foreground": before each step, yield the GUI to a user
    command started meanwhile, then resume with a fresh look (tasks.gui_checkpoint)."""

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        try:
            resumed = tasks.gui_checkpoint(computer.gui_lock)
        except TimeoutError:
            computer.session.stop_reason = "the screen stayed busy with another task."
            event.cancel_tool = "The screen is busy. Stop."
            return
        if resumed:
            computer.begin_session()  # old screenshot and pointer position are stale now
            computer.session.asked = True  # an interrupted run is never recorded as a flow
            event.cancel_tool = RESUMED


def _acquire_gui(cancel: Any) -> bool:
    """Wait for the GUI lock while a paused task hands it over (bounded, stoppable)."""
    deadline = time.monotonic() + GUI_PAUSE_MAX_S
    while not computer.gui_lock.acquire(timeout=LOCK_POLL_S):
        if cancel.is_set() or time.monotonic() > deadline or not _gui_handover_expected():
            return False
    return True


def _gui_handover_expected() -> bool:
    """Only wait when the lock holder is a task that will pause for us; else busy at once."""
    me = tasks.current()
    return me is not None and any(
        me.id in t.paused_by or t.status == "paused" for t in tasks.running()
    )


# --- Recorded flows (harness Layer 1 for GUI tasks) ----------------------------------------------

STEP_TOOLS = {"open_app", "ax_press", "click", "key", "scroll"}
UNRECORDABLE = {"type_text", "run_shortcut"}  # typed text may be personal; shortcuts always ask


class FlowMismatch(Exception):
    """The screen isn't what the recorded flow expects: let the agent do it."""


class FlowRecorder(HookProvider):
    """Collect the successful input steps of one computer task."""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.spoiled = False

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    def after_tool(self, event: AfterToolCallEvent) -> None:
        name = str(event.tool_use.get("name", ""))
        if name in UNRECORDABLE:
            self.spoiled = True
        if name not in STEP_TOOLS or (event.result or {}).get("status") != "success":
            return
        if name in ("click", "key") and computer.session.failures:
            return  # it didn't visibly work: not part of the recipe
        step = {"tool": name, "args": dict(event.tool_use.get("input") or {})}
        if name == "click":
            step["expect"] = computer.session.last_click
        self.steps.append(step)


def flow_key(goal: str, app: str) -> str:
    """ponytail: exact normalised goal text; the brain phrasing a goal differently is a miss."""
    return f"{safety.normalise(app)}|{safety.normalise(goal)}"


def _load_flows() -> dict[str, Any]:
    try:
        return json.loads(COMPUTER_FLOWS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_flow(key: str, steps: list[dict[str, Any]]) -> None:
    flows = {**_load_flows(), key: {"at": time.time(), "steps": steps}}
    try:
        LOG_DIR.mkdir(exist_ok=True)
        COMPUTER_FLOWS_FILE.write_text(json.dumps(flows, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # a lost recipe only costs model calls next time


def replay_flow(key: str, cancel: Any) -> bool:
    """Run a recorded flow with no model: True if every step verified, False if none is stored,
    FlowMismatch otherwise. ConfirmationDeclined still ends the task: each tool runs its gate."""
    flow = _load_flows().get(key)
    if not flow or time.time() - flow.get("at", 0) > COMPUTER_FLOW_TTL_S:
        return False
    tools = {t.tool_name: t for t in [*computer.COMPUTER_TOOLS, *ax.AX_TOOLS]}
    for step in flow["steps"]:
        if cancel.is_set():
            raise FlowMismatch("cancelled")
        _check_step(step)
        failures = computer.session.failures
        try:
            tools[step["tool"]](**step["args"])
        except (ToolError, KeyError, TypeError) as error:
            raise FlowMismatch(str(error)) from error
        if computer.session.failures > failures or computer.session.stop_reason:
            raise FlowMismatch("a step didn't visibly work")
    return True


def _check_step(step: dict[str, Any]) -> None:
    """A recorded click only replays onto the same screen size, app and AX labels."""
    if step["tool"] != "click":
        return
    shot = computer.session.shot = screen.capture_display()
    expect = step.get("expect") or {}
    if [shot.width, shot.height] != expect.get("size"):
        raise FlowMismatch("screen size changed")
    x, y = step["args"].get("x", -1), step["args"].get("y", -1)
    try:
        point = screen.image_to_screen(x, y, shot.width, shot.height, shot.frame)
    except ToolError as error:
        raise FlowMismatch(str(error)) from error
    if ax.front_app()[0] != expect.get("app"):
        raise FlowMismatch("a different app is in front")
    if ax.click_facts(ax.element_at(*point)).labels != expect.get("labels"):
        raise FlowMismatch("the target isn't there")


# --- Running a task ------------------------------------------------------------------------------


def _usage_cost(agent: Any) -> float:
    from zoya.orchestrator import task_cost_usd

    usage = agent.event_loop_metrics.accumulated_usage
    model = os.environ.get("BRAIN_MODEL", "")
    return task_cost_usd(model, usage.get("inputTokens", 0), usage.get("outputTokens", 0))


def _remaining_budget(parent: Any) -> float:
    """The cap is per task: the brain's spend and every earlier computer_task come off it.
    ponytail: the brain's own TaskLimits still ignores sub-agent spend for its (text) calls."""
    spent = _usage_cost(parent) + float(parent.state.get(SPENT_KEY) or 0.0)
    return max(0.0, PER_TASK_COST_CAP_USD - spent)


def build_computer_agent(cost_cap_usd: float, recorder: FlowRecorder | None = None) -> Agent:
    from zoya.models import get_model
    from zoya.orchestrator import TaskLimits, narrate_tool

    return Agent(
        model=get_model("brain"),
        system_prompt=COMPUTER_PROMPT,
        tools=[*computer.COMPUTER_TOOLS, *ax.AX_TOOLS, narrate_tool],
        hooks=[
            TaskLimits(os.environ.get("BRAIN_MODEL", ""), cost_cap_usd),
            *([recorder] if recorder else []),
            ScreenshotPruner(),
            GiveUp(),
            GuiPause(),
            tasks.StepTracker(),
            safety.ConfirmationGate(),  # last: sees the final tool call
        ],
        tool_executor=SequentialToolExecutor(),
        callback_handler=None,
        trace_attributes={"zoya.component": "computer_agent"},
    )


def run_computer_task(
    goal: str, cost_cap_usd: float = PER_TASK_COST_CAP_USD, parent: Any = None
) -> str:
    """Run one GUI goal under the lock: a recorded flow first, else the agent. Raises
    ConfirmationDeclined / TaskLimitExceeded / TaskCancelled like the orchestrator."""
    from zoya.orchestrator import cancel_signal

    _cancel = cancel_signal()
    if not _acquire_gui(_cancel):
        raise ToolError(BUSY)
    started = time.monotonic()
    try:
        computer.begin_session()
        key = flow_key(goal, ax.front_app()[0])
        try:
            if replay_flow(key, _cancel):
                elapsed = round((time.monotonic() - started) * MS_PER_S)
                computer.log_stage("computer_task", outcome="replayed", computer_ms=elapsed)
                return REPLAYED
        except FlowMismatch as mismatch:
            computer.log_stage("computer_flow_mismatch", reason=str(mismatch)[:80])
            computer.begin_session()
        finished = _run_step_loop(goal, key, _cancel, started)
        if finished is not None:
            return finished
        return _run_agent(goal, key, cost_cap_usd, parent, started)
    finally:
        computer.gui_lock.release()


def _run_step_loop(goal: str, key: str, cancel: Any, started: float) -> str | None:
    """The Jev loop first: no language model at all when Jev can finish the goal alone (D82).

    None means it could not finish and the language-model agent takes over on the same screen.
    """
    outcome = step_loop.run(goal, [], cancel)
    computer.log_stage(
        "computer_step_loop",
        outcome="done" if outcome.done else "escalated",
        reason=outcome.reason[:80],
        steps=outcome.steps,
        jev_calls=outcome.jev_calls,
        jev_ms=outcome.jev_ms,
        model_calls=0,
        computer_ms=round((time.monotonic() - started) * MS_PER_S),
    )
    if not outcome.done:
        return None
    if outcome.recorded and not computer.session.asked:
        save_flow(key, outcome.recorded)
    return _spoken(outcome.pressed)


def _spoken(pressed: list[str]) -> str:
    if not pressed:
        return "That was already done."
    return f"Done — I pressed {safety.spoken_name([pressed[-1]]) or pressed[-1]}."


def _run_agent(goal: str, key: str, cost_cap_usd: float, parent: Any, started: float) -> str:
    from zoya.orchestrator import TaskCancelled, TaskLimitExceeded, cancel_signal

    _cancel = cancel_signal()
    recorder = FlowRecorder()
    agent = build_computer_agent(cost_cap_usd, recorder)
    outcome = "done"
    try:
        result = agent(goal, cancel_signal=_cancel)
        if result.stop_reason == "cancelled" or _cancel.is_set():
            outcome = "cancelled"
            raise TaskCancelled
        if recorder.steps and not recorder.spoiled and not computer.session.asked:
            save_flow(key, recorder.steps)
        return str(result).strip() or "Done."
    except EventLoopException as wrapped:
        cause = wrapped.original_exception
        if isinstance(cause, ComputerStopped):
            outcome = "gave_up"
            return f"I stopped: {cause} Nothing else was changed."
        if isinstance(cause, TaskLimitExceeded | safety.ConfirmationDeclined):
            outcome = type(cause).__name__
            raise cause from wrapped
        raise
    finally:
        _account(agent, parent, outcome, started)


def _account(agent: Agent, parent: Any, outcome: str, started: float) -> None:
    usage = agent.event_loop_metrics.accumulated_usage
    if parent is not None:
        parent.state.set(SPENT_KEY, float(parent.state.get(SPENT_KEY) or 0.0) + _usage_cost(agent))
    computer.log_stage(
        "computer_task",
        outcome=outcome,
        computer_ms=round((time.monotonic() - started) * MS_PER_S),
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        cached_tokens=usage.get("cacheReadInputTokens", 0),
        failures=computer.session.failures,
    )


@tool(context=True)
def computer_task(goal: str, tool_context: ToolContext) -> str:
    """Operate a Mac app with the mouse and keyboard: System Settings, Finder, Preview, any app
    without a direct tool or website. Slower than direct tools: use only when they can't do it.

    Args:
        goal: The complete goal in plain words, e.g. "Turn on dark mode in System Settings".
    """
    parent = tool_context.agent
    return run_computer_task(goal, _remaining_budget(parent), parent)


TOOLS = [computer_task]
