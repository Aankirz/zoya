"""computer_agent (§9.5, §9.6): a Strands Agent that operates Mac apps, exposed to the brain as one
tool, `computer_task(goal)`.

Harness, cheapest first (docs/research/harness.md): replay a recorded flow (0 model calls) →
the user's Shortcuts → AX (T1) → pixels (T3). Strands provides the agent loop, hooks, the
sequential executor and cancellation; Zoya adds the GUI lock, screenshot pruning, the give-up
rule and the gate.

- One GUI task at a time (`computer.gui_lock`); "Zoya, stop" cancels it (orchestrator._cancel).
- The safety gate is registered last, as on the orchestrator (safety.ConfirmationGate); every
  input tool also runs Guard 2 on its real target itself.
- Only the last KEEP_SCREENSHOTS screenshots stay in context (§9.3).
- Three failed attempts in a row, or the user moving the mouse, end the task honestly.
- Its cost counts against what is left of the task's cap.

Strands 1.55.1 source: tools/decorator.py (`@tool(context=True)` → ToolContext.agent),
hooks/events.py (BeforeModelCallEvent), agent/agent.py (`cancel_signal`).
"""

from __future__ import annotations

import os
import time
from typing import Any

from strands import Agent, ToolContext, tool
from strands.hooks import BeforeModelCallEvent, HookProvider, HookRegistry
from strands.tools.executors import SequentialToolExecutor
from strands.types.exceptions import EventLoopException

from zoya import safety
from zoya.config import KEEP_SCREENSHOTS, PER_TASK_COST_CAP_USD
from zoya.prompts import COMPUTER_PROMPT
from zoya.tools import ToolError, ax, computer

BUSY = "I'm already using the screen for another task."
PRUNED_SCREENSHOT = {"text": "[older screenshot removed]"}
MS_PER_S = 1000


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


SPENT_KEY = "computer_spent_usd"  # on the brain agent's state: earlier computer_task calls


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


def build_computer_agent(cost_cap_usd: float) -> Agent:
    from zoya.models import get_model
    from zoya.orchestrator import TaskLimits, narrate_tool

    return Agent(
        model=get_model("brain"),
        system_prompt=COMPUTER_PROMPT,
        tools=[*computer.COMPUTER_TOOLS, *ax.AX_TOOLS, narrate_tool],
        hooks=[
            TaskLimits(os.environ.get("BRAIN_MODEL", ""), cost_cap_usd),
            ScreenshotPruner(),
            GiveUp(),
            safety.ConfirmationGate(),  # last: sees the final tool call
        ],
        tool_executor=SequentialToolExecutor(),
        callback_handler=None,
        trace_attributes={"zoya.component": "computer_agent"},
    )


def run_computer_task(
    goal: str, cost_cap_usd: float = PER_TASK_COST_CAP_USD, parent: Any = None
) -> str:
    """Run one GUI goal under the lock. Raises ConfirmationDeclined / TaskLimitExceeded /
    TaskCancelled like the orchestrator, so the task ends as itself."""
    from zoya.orchestrator import TaskCancelled, TaskLimitExceeded, _cancel

    if not computer.gui_lock.acquire(blocking=False):
        raise ToolError(BUSY)
    started = time.monotonic()
    agent = build_computer_agent(cost_cap_usd)
    outcome = "done"
    try:
        computer.begin_session()
        result = agent(goal, cancel_signal=_cancel)
        if result.stop_reason == "cancelled" or _cancel.is_set():
            outcome = "cancelled"
            raise TaskCancelled
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
        computer.gui_lock.release()
        usage = agent.event_loop_metrics.accumulated_usage
        if parent is not None:
            parent.state.set(
                SPENT_KEY, float(parent.state.get(SPENT_KEY) or 0.0) + _usage_cost(agent)
            )
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
