"""Command handling: router → fast T0 tool or Strands orchestrator (§9.3, §13.5).

`handle_command` is the one entry point for a typed (later spoken) command. It
logs per-stage timing (§13.5.1) to logs/timing.log and, when an OTLP endpoint
is configured, exports the same numbers plus Strands' agent traces via
OpenTelemetry to CloudWatch/X-Ray (STACK §8).

Tracing docs: https://strandsagents.com/docs/user-guide/observability-evaluation/traces/
CloudWatch OTLP endpoint (SigV4, via the ADOT collector):
https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-OTLPEndpoint.html
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from strands import Agent, tool
from strands.hooks import (
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    HookProvider,
    HookRegistry,
)
from strands.tools.executors import SequentialToolExecutor
from strands.types.exceptions import EventLoopException

from zoya import aws, events, harness, safety, speech, tasks
from zoya.config import (
    LOG_DIR,
    MAX_TOOL_CALLS_PER_TASK,
    MODEL_PRICES_USD_PER_1M,
    PER_TASK_COST_CAP_USD,
    TIMING_LOG,
    UNKNOWN_MODEL_PRICE_USD_PER_1M,
)
from zoya.prompts import ORCHESTRATOR_PROMPT
from zoya.router import RouteDecision, route
from zoya.tools import ToolError, collect_tools
from zoya.tools.memory import recent_corrections

log = logging.getLogger(__name__)

TOKENS_PER_PRICE_UNIT = 1_000_000
MS_PER_S = 1000
LOG_COMMAND_MAX_CHARS = 60
STOPPED_MESSAGE = "Okay, stopped."
GENERIC_FAILURE = "Sorry, something went wrong. Please try again."
LIMIT_MESSAGE = "I've stopped this task because it was taking too many steps."
IDLE_MESSAGE = "Nothing is running."
OPEN_APP_FALLBACK = "open_app_fallback"
DECLINED = "confirmation_declined"  # the safety gate already played cancel and spoke
STREAMED = "brain"  # the brain ran and spoke as it streamed
SKILL_FALLBACK = "skill_fallback"  # a skill action failed; the brain retried with that skill
MAX_CONVERSATION_TURNS = 6  # follow-ups keep context; older turns drop to bound token cost
SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


@dataclass(frozen=True)
class CommandResult:
    task_id: str
    decision: RouteDecision
    spoken: str
    ok: bool
    timings_ms: dict[str, int]


# --- Money and step limits -------------------------------------------------------


class TaskLimitExceeded(Exception):
    """Raised inside the agent loop to hard-stop a task (§12.1 bounded autonomy)."""


def task_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICES_USD_PER_1M.get(
        model_id, UNKNOWN_MODEL_PRICE_USD_PER_1M
    )
    return (input_tokens * input_price + output_tokens * output_price) / TOKENS_PER_PRICE_UNIT


class TaskLimits(HookProvider):
    """Before every model call: stop if the task passed $PER_TASK_COST_CAP_USD or 40 tool calls.

    Inside a Task Manager task every agent (orchestrator, document agent) adds its spend to the
    task's ledger, so sub-agents share one cap instead of each getting a fresh $0.50.
    """

    def __init__(self, model_id: str, cost_cap_usd: float = PER_TASK_COST_CAP_USD) -> None:
        self.model_id = model_id
        self.cost_cap_usd = cost_cap_usd
        self.tool_calls = 0
        self.recorded_usd = 0.0  # this agent's spend already added to the task ledger

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._count_tool_call)
        registry.add_callback(BeforeModelCallEvent, self._check_limits)
        registry.add_callback(AfterModelCallEvent, self._record)

    def _count_tool_call(self, _event: AfterToolCallEvent) -> None:
        self.tool_calls += 1

    def _record(self, event: Any) -> float:
        """Add this agent's new spend to its task; returns the task's (or this agent's) total."""
        usage = event.agent.event_loop_metrics.accumulated_usage
        tokens_in, tokens_out = usage.get("inputTokens", 0), usage.get("outputTokens", 0)
        own = task_cost_usd(self.model_id, tokens_in, tokens_out)
        delta, self.recorded_usd = own - self.recorded_usd, own
        return tasks.add_spend(delta) if tasks.current() is not None else own

    def _check_limits(self, event: BeforeModelCallEvent) -> None:
        cost = self._record(event)
        if cost >= self.cost_cap_usd:
            raise TaskLimitExceeded(f"cost cap ${self.cost_cap_usd:.2f} reached (${cost:.4f})")
        if self.tool_calls >= MAX_TOOL_CALLS_PER_TASK:
            raise TaskLimitExceeded(f"{MAX_TOOL_CALLS_PER_TASK} tool calls reached")


class TaskCancelled(Exception):
    """The user said stop (§11.3)."""


class SentenceStream:
    """Split streamed model text into whole sentences so the first one is spoken at once."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        parts = SENTENCE_END.split(self._buffer + text)
        self._buffer = parts.pop()
        return [part.strip() for part in parts if part.strip()]

    def flush(self) -> str:
        rest, self._buffer = self._buffer.strip(), ""
        return rest


# --- Orchestrator -----------------------------------------------------------------

_cancel = threading.Event()  # outside a Task Manager task (tests, evals); tasks have their own
_conversation: list[list[Any]] = []  # recent turns, each the messages one run added


def cancel_signal() -> threading.Event:
    """The stop flag of the task running on this thread ("stop the presentation" sets only its)."""
    task = tasks.current()
    return task.cancel if task is not None else _cancel


@tool(name="narrate")
def narrate_tool(text: str) -> str:
    """Say a short progress update (under 12 words) to the user out loud."""
    tasks.set_step(text)
    tasks.say(text)
    return "Said."


def brain_inputs(skill: str = "") -> tuple[str, list[Any], list[Any]]:
    """(system prompt, tools, plugins), byte-stable per skill so OpenAI caches the prefix.

    A picked skill gets its body in the prompt (no `skills` round trip) and only its tools. No pick:
    every tool plus Strands `AgentSkills`, which lists the catalogue and loads a body on demand.
    """
    from zoya.agents.document_agent import document_agent_tool

    document_tool = document_agent_tool()  # a fresh sub-agent per task: two tasks never share one
    tools = harness.all_tools() | {
        narrate_tool.tool_name: narrate_tool,
        document_tool.tool_name: document_tool,
    }
    if skill:
        names = harness.skill_tool_names(skill)
        return (
            harness.skill_prompt(ORCHESTRATOR_PROMPT, skill),
            [tools[name] for name in names if name in tools],
            [],
        )
    from strands.vended_plugins.skills import AgentSkills

    ordered = [tools[name] for name in sorted(tools)]
    return ORCHESTRATOR_PROMPT, ordered, [AgentSkills(skills=list(harness.catalog().values()))]


def build_orchestrator(
    cost_cap_usd: float = PER_TASK_COST_CAP_USD,
    messages: list[Any] | None = None,
    callback_handler: Any = None,
    skill: str = "",
) -> Agent:
    """A fresh Agent per task (AUDIT B6), seeded with recent conversation for follow-ups."""
    from zoya.models import get_model

    prompt, tools, plugins = brain_inputs(skill)
    limits = TaskLimits(os.environ.get("BRAIN_MODEL", ""), cost_cap_usd)
    return Agent(
        model=get_model("brain", cache_key=harness.cache_key(skill)),
        system_prompt=prompt,
        tools=tools,
        plugins=plugins,
        messages=messages,
        # The gate goes last so it sees the final tool call (safety.ConfirmationGate). Tools run one
        # at a time: nothing else speaks or clicks while a confirmation waits for the user.
        hooks=[limits, tasks.StepTracker(), safety.ConfirmationGate()],
        tool_executor=SequentialToolExecutor(),
        callback_handler=callback_handler,
        trace_attributes={"zoya.component": "orchestrator"},
    )


def _speak_stream(sentences: SentenceStream, spoken: list[str] | None = None) -> Any:
    def handler(**kwargs: Any) -> None:
        if cancel_signal().is_set():
            return  # stopped: Strands ends the stream at its next checkpoint; say nothing more
        for sentence in sentences.feed(kwargs.get("data", "")):
            tasks.say(sentence)
            if spoken is not None:
                spoken.append(sentence)

    return handler


def _record_usage(agent: Agent, timings: dict[str, int]) -> None:
    """Tokens next to the timings; cached_tokens shows whether OpenAI's prefix cache applied."""
    usage = agent.event_loop_metrics.accumulated_usage
    timings["input_tokens"] = usage.get("inputTokens", 0)
    timings["output_tokens"] = usage.get("outputTokens", 0)
    timings["cached_tokens"] = usage.get("cacheReadInputTokens", 0)
    timings["brain_calls"] = getattr(agent.event_loop_metrics, "cycle_count", 0)


def with_corrections(command: str) -> str:
    """§13.5.6: recent corrections ride with the request (dynamic part), never in the prefix."""
    corrections = recent_corrections()
    if not corrections:
        return command
    return f"{command}\n[Recent corrections from the user: {'; '.join(corrections)}]"


def run_orchestrator(command: str, timings: dict[str, int] | None = None, skill: str = "") -> str:
    """Speak the brain's answer sentence by sentence as it streams; return the full text."""
    history = [message for turn in _conversation for message in turn]
    sentences, spoken = SentenceStream(), []
    agent = build_orchestrator(
        messages=list(history), callback_handler=_speak_stream(sentences, spoken), skill=skill
    )
    if timings is not None:
        timings[STREAMED] = 1
    try:
        # Native cancellation (strands 1.55.1 Agent.__call__ cancel_signal): stops mid-stream,
        # before tool execution and between steps, returning stop_reason="cancelled" (§11.3).
        result = _invoke(agent, with_corrections(command))
    except TaskLimitExceeded as limit:
        _record_usage(agent, timings if timings is not None else {})
        log.warning("task stopped: %s", limit)
        tasks.say(LIMIT_MESSAGE)
        return LIMIT_MESSAGE
    except safety.ConfirmationDeclined:
        _record_usage(agent, timings if timings is not None else {})
        # What the user heard, not the model-facing "do not try again": a later, fresh request
        # for the same thing must be asked again, not refused (Phase 3 replay).
        remember_turn(command, f"{safety.CANCELLED_SAY} [the user did not confirm]")
        raise
    _record_usage(agent, timings if timings is not None else {})
    if result.stop_reason == "cancelled" or cancel_signal().is_set():
        _remember_interrupted(command, spoken)
        raise TaskCancelled
    tasks.say(sentences.flush())
    _conversation.append(agent.messages[len(history) :])
    del _conversation[:-MAX_CONVERSATION_TURNS]
    return str(result).strip() or "Done."


def _invoke(agent: Agent, command: str) -> Any:
    """Strands wraps exceptions raised in hooks into EventLoopException (strands 1.55.1
    event_loop/event_loop.py event_loop_cycle); unwrap ours so a cap or a declined confirmation
    ends the task as itself, not as "something went wrong" (found in the Phase 3 replay)."""
    try:
        return agent(command, cancel_signal=cancel_signal())
    except EventLoopException as wrapped:
        cause = wrapped.original_exception
        if isinstance(cause, TaskLimitExceeded | safety.ConfirmationDeclined):
            raise cause from wrapped
        raise


def _remember_interrupted(command: str, spoken: list[str]) -> None:
    """Keep what the user actually heard, so "continue" works after "Zoya, stop".

    ponytail: sentences queued for speech, not exactly what played before the cut (LiveKit syncs
    to playback); a half-heard last sentence is kept whole.
    """
    heard = " ".join(spoken) or "(nothing yet)"
    remember_turn(command, f"{heard} [interrupted by the user]")


def remember_turn(command: str, reply: str) -> None:
    """Fast-path turns join the conversation too: "find it on the browser" must know what "it" is
    (owner's run searched the previous song instead of MrBeast)."""
    _conversation.append(
        [
            {"role": "user", "content": [{"text": command}]},
            {"role": "assistant", "content": [{"text": reply}]},
        ]
    )
    del _conversation[:-MAX_CONVERSATION_TURNS]


# --- Fast path and entry point ----------------------------------------------------


def run_skill(decision: RouteDecision, timings: dict[str, int]) -> str:
    """Layer 1 action (0 model calls) when one was picked; on failure or no action, the brain with
    only that skill's tools. A declined confirmation is never retried."""
    if not decision.tool:
        return run_orchestrator(decision.text, timings, decision.skill)
    try:
        spoken = harness.run_action(decision.tool, decision.args)
    except ToolError as error:
        if decision.tool not in harness.action_tools():
            raise  # a plain tool's answer is final ("I can't remember card numbers")
        log.warning("skill action %s failed (%s): brain retries", decision.tool, error)
        timings[SKILL_FALLBACK] = 1
        return run_orchestrator(decision.text, timings, decision.skill)
    if decision.source == "model":
        harness.learn_pick(
            decision.text, harness.SkillMatch(decision.skill, decision.tool, decision.args)
        )
    return safety.UNTRUSTED_TAG.sub("", spoken).strip()  # spoken to the user, not fed to a model


def run_fast_tool(decision: RouteDecision) -> str:
    # No Agent, so no hooks on this path: only free tools may run here (safety registry).
    if not safety.fast_tool_allowed(decision.tool or ""):
        raise ToolError("I can't do that directly.")
    from zoya.agents.screen_describer import describe_screen  # the one agent tool allowed here

    tools = {t.tool_name: t for t in [*collect_tools("zoya.tools"), describe_screen]}
    return tools[decision.tool](**decision.args)


def _execute(decision: RouteDecision, timings: dict[str, int]) -> tuple[str, bool]:
    started = time.monotonic()
    stage = "orchestrator_ms" if decision.route == "orchestrator" else "tool_ms"
    try:
        if decision.route == "stop":
            return STOPPED_MESSAGE, True
        if decision.route == "skill":
            return run_skill(decision, timings), True
        if decision.route == "fast":
            try:
                return run_fast_tool(decision), True
            except ToolError:
                if decision.tool != "open_app":
                    raise
                # "open YouTube MrBeast" is no installed app: let the brain try the web instead.
                timings[OPEN_APP_FALLBACK] = 1
                return run_orchestrator(decision.text, timings), True
        return run_orchestrator(decision.text, timings), True
    except ToolError as error:
        return str(error), False
    except safety.ConfirmationDeclined as declined:
        if str(declined) == safety.STOPPED_TO_MODEL:
            return STOPPED_MESSAGE, False
        timings[DECLINED] = 1  # the gate played cancel and said what happened
        said = str(declined)
        return (safety.CANCELLED_SAY if said == safety.ALREADY_DECLINED else said), False
    except (KeyboardInterrupt, TaskCancelled):
        return STOPPED_MESSAGE, False
    except Exception:  # noqa: BLE001 — never crash on a command; say so politely
        log.exception("command failed")
        return GENERIC_FAILURE, False
    finally:
        timings[stage] = round((time.monotonic() - started) * MS_PER_S)


def handle_command(text: str, pre_timings: dict[str, int] | None = None) -> CommandResult:
    """Run one command. `pre_timings` (voice stages such as stt_ms) go into the timing log."""
    task = tasks.current()
    task_id = task.id if task is not None else uuid.uuid4().hex[:12]
    started = time.monotonic()
    if task is None:
        _cancel.clear()
    safety.begin_task(task_id)
    with trace.get_tracer("zoya").start_as_current_span("zoya.command") as span:
        decision = route(text)
        timings = {**(pre_timings or {}), **decision.timings_ms}
        events.emit(events.TaskEvent(task_id, "started", text, decision.route))
        spoken, ok = _execute(decision, timings)
        # Fast path target is router + tool (Done-when #2); speech is queued, not waited on.
        timings["total_ms"] = round((time.monotonic() - started) * MS_PER_S)
        span.set_attributes({f"zoya.{k}": v for k, v in timings.items()})
        span.set_attributes({"zoya.route": decision.route, "zoya.tool": decision.tool or ""})
    outcome = "stop" if decision.route == "stop" or spoken == STOPPED_MESSAGE else "success"
    declined = DECLINED in timings
    stopped_by_name = task is not None and task.cancel.is_set()  # the stop already spoke for it
    if not declined and not stopped_by_name:
        shared_done = ok and task is not None and task.shared and outcome == "success"
        events.emit(
            events.EarconEvent(
                "complete" if shared_done else outcome if ok or outcome == "stop" else "error"
            )
        )
    streamed = STREAMED in timings
    if (not streamed or not ok) and not declined and not stopped_by_name:
        tasks.say(spoken)  # the orchestrator already spoke as it streamed
    if decision.route in ("fast", "skill") and not streamed:
        remember_turn(text, spoken)
    result = CommandResult(task_id, decision, spoken, ok, timings)
    _log_timing(text, result)
    events.emit(events.TaskEvent(task_id, "done" if ok else "failed", text, decision.route, spoken))
    return result


# --- Voice-loop task functions (§9.2, §9.13: several tasks through zoya/tasks.py) ------------


def start_task(
    command: str,
    pre_timings: dict[str, int] | None = None,
    on_done: Callable[[CommandResult], None] | None = None,
) -> tasks.Task | None:
    """Run `command` as a Task Manager task so the listener stays free. None = three are running
    (the caller says tasks.FULL_MESSAGE)."""

    def run(_task: tasks.Task) -> None:
        result = handle_command(command, pre_timings)
        if on_done:
            on_done(result)

    return tasks.spawn(command, run)


tasks.set_runner(lambda command: start_task(command))  # queued commands start when a slot frees


def stop_task(name: str = "") -> str:
    """ "Zoya, stop": the task asking or last speaking, speech cut now (§11.3). With a name ("the
    presentation", "everything"): only those tasks, and nobody else's speech or confirmation."""
    if name.strip():
        return tasks.stop(name)
    said = tasks.stop_last()
    if not tasks.running():
        _cancel.set()
        safety.cancel_pending()  # outside tasks: whatever confirmation waits ends with no token
    speech.cancel()
    return said or STOPPED_MESSAGE


def task_status(name: str = "") -> str:
    return tasks.task_status(name)


def current_command() -> str:
    """The command of the task on this thread (else the newest), for Flow 10 resume."""
    task = tasks.current()
    if task is not None:
        return task.command
    running = tasks.running()
    return running[-1].command if running else ""


def model_calls(result: CommandResult) -> int:
    """Done-when #11/#12 evidence: router-model calls plus brain cycles for this command."""
    router = 1 if "model_ms" in result.timings_ms else 0
    return router + result.timings_ms.get("brain_calls", 0)


def _log_timing(text: str, result: CommandResult) -> None:
    record = {
        "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "task_id": result.task_id,
        "route": result.decision.route,
        "source": result.decision.source,
        "skill": result.decision.skill or None,
        "tool": result.decision.tool,
        "model_calls": model_calls(result),
        "ok": result.ok,
        **result.timings_ms,
        "command": text[:LOG_COMMAND_MAX_CHARS],
    }
    LOG_DIR.mkdir(exist_ok=True)
    with TIMING_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    history = {k: str(v) for k, v in record.items() if v is not None}
    aws.record_task(history)


def setup_tracing() -> str:
    """Export Strands + Zoya spans over OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return "off (set OTEL_EXPORTER_OTLP_ENDPOINT to an ADOT collector)"
    from strands.telemetry import StrandsTelemetry

    StrandsTelemetry().setup_otlp_exporter()
    return f"OTLP → {os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']}"
