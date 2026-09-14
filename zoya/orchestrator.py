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
from strands.hooks import AfterToolCallEvent, BeforeModelCallEvent, HookProvider, HookRegistry

from zoya import aws, events, speech
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

log = logging.getLogger(__name__)

TOKENS_PER_PRICE_UNIT = 1_000_000
MS_PER_S = 1000
LOG_COMMAND_MAX_CHARS = 60
STOPPED_MESSAGE = "Okay, stopped."
GENERIC_FAILURE = "Sorry, something went wrong. Please try again."
LIMIT_MESSAGE = "I've stopped this task because it was taking too many steps."
IDLE_MESSAGE = "Nothing is running."
OPEN_APP_FALLBACK = "open_app_fallback"
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
    """Before every model call: stop if the task passed $PER_TASK_COST_CAP_USD or 40 tool calls."""

    def __init__(self, model_id: str, cost_cap_usd: float = PER_TASK_COST_CAP_USD) -> None:
        self.model_id = model_id
        self.cost_cap_usd = cost_cap_usd
        self.tool_calls = 0

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._count_tool_call)
        registry.add_callback(BeforeModelCallEvent, self._check_limits)

    def _count_tool_call(self, _event: AfterToolCallEvent) -> None:
        self.tool_calls += 1

    def _check_limits(self, event: BeforeModelCallEvent) -> None:
        usage = event.agent.event_loop_metrics.accumulated_usage
        cost = task_cost_usd(self.model_id, usage["inputTokens"], usage["outputTokens"])
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

_cancel = threading.Event()  # ponytail: one task at a time; Phase 6 gives each task its own
_conversation: list[list[Any]] = []  # recent turns, each the messages one run added
_running: dict[str, str] = {}  # task_id → command
_running_lock = threading.Lock()


@tool(name="narrate")
def narrate_tool(text: str) -> str:
    """Say a short progress update (under 12 words) to the user out loud."""
    speech.narrate(text)
    return "Said."


def build_orchestrator(
    cost_cap_usd: float = PER_TASK_COST_CAP_USD,
    messages: list[Any] | None = None,
    callback_handler: Any = None,
) -> Agent:
    """A fresh Agent per task (AUDIT B6), seeded with recent conversation for follow-ups."""
    from zoya.models import get_model

    tools = [*collect_tools("zoya.tools", "zoya.agents"), narrate_tool]
    limits = TaskLimits(os.environ.get("BRAIN_MODEL", ""), cost_cap_usd)
    return Agent(
        model=get_model("brain"),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=tools,
        messages=messages,
        hooks=[limits],
        callback_handler=callback_handler,
        trace_attributes={"zoya.component": "orchestrator"},
    )


def _speak_stream(sentences: SentenceStream, spoken: list[str] | None = None) -> Any:
    def handler(**kwargs: Any) -> None:
        if _cancel.is_set():
            return  # stopped: Strands ends the stream at its next checkpoint; say nothing more
        for sentence in sentences.feed(kwargs.get("data", "")):
            speech.narrate(sentence)
            if spoken is not None:
                spoken.append(sentence)

    return handler


def _record_usage(agent: Agent, timings: dict[str, int]) -> None:
    """Tokens next to the timings; cached_tokens shows whether OpenAI's prefix cache applied."""
    usage = agent.event_loop_metrics.accumulated_usage
    timings["input_tokens"] = usage.get("inputTokens", 0)
    timings["output_tokens"] = usage.get("outputTokens", 0)
    timings["cached_tokens"] = usage.get("cacheReadInputTokens", 0)


def run_orchestrator(command: str, timings: dict[str, int] | None = None) -> str:
    """Speak the brain's answer sentence by sentence as it streams; return the full text."""
    history = [message for turn in _conversation for message in turn]
    sentences, spoken = SentenceStream(), []
    agent = build_orchestrator(
        messages=list(history), callback_handler=_speak_stream(sentences, spoken)
    )
    try:
        # Native cancellation (strands 1.55.1 Agent.__call__ cancel_signal): stops mid-stream,
        # before tool execution and between steps, returning stop_reason="cancelled" (§11.3).
        result = agent(command, cancel_signal=_cancel)
    except TaskLimitExceeded as limit:
        _record_usage(agent, timings if timings is not None else {})
        log.warning("task stopped: %s", limit)
        speech.narrate(LIMIT_MESSAGE)
        return LIMIT_MESSAGE
    _record_usage(agent, timings if timings is not None else {})
    if result.stop_reason == "cancelled" or _cancel.is_set():
        _remember_interrupted(command, spoken)
        raise TaskCancelled
    speech.narrate(sentences.flush())
    _conversation.append(agent.messages[len(history) :])
    del _conversation[:-MAX_CONVERSATION_TURNS]
    return str(result).strip() or "Done."


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


def run_fast_tool(decision: RouteDecision) -> str:
    tools = {t.tool_name: t for t in collect_tools("zoya.tools")}
    return tools[decision.tool](**decision.args)


def _execute(decision: RouteDecision, timings: dict[str, int]) -> tuple[str, bool]:
    started = time.monotonic()
    stage = "orchestrator_ms" if decision.route == "orchestrator" else "tool_ms"
    try:
        if decision.route == "stop":
            return STOPPED_MESSAGE, True
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
    except (KeyboardInterrupt, TaskCancelled):
        return STOPPED_MESSAGE, False
    except Exception:  # noqa: BLE001 — never crash on a command; say so politely
        log.exception("command failed")
        return GENERIC_FAILURE, False
    finally:
        timings[stage] = round((time.monotonic() - started) * MS_PER_S)


def handle_command(text: str, pre_timings: dict[str, int] | None = None) -> CommandResult:
    """Run one command. `pre_timings` (voice stages such as stt_ms) go into the timing log."""
    task_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    _cancel.clear()
    with _running_lock:
        _running[task_id] = text
    with trace.get_tracer("zoya").start_as_current_span("zoya.command") as span:
        decision = route(text)
        timings = {**(pre_timings or {}), **decision.timings_ms}
        events.emit(events.TaskEvent(task_id, "started", text, decision.route))
        try:
            spoken, ok = _execute(decision, timings)
        finally:
            with _running_lock:
                _running.pop(task_id, None)
        # Fast path target is router + tool (Done-when #2); speech is queued, not waited on.
        timings["total_ms"] = round((time.monotonic() - started) * MS_PER_S)
        span.set_attributes({f"zoya.{k}": v for k, v in timings.items()})
        span.set_attributes({"zoya.route": decision.route, "zoya.tool": decision.tool or ""})
    outcome = "stop" if decision.route == "stop" or spoken == STOPPED_MESSAGE else "success"
    events.emit(events.EarconEvent(outcome if ok or outcome == "stop" else "error"))
    streamed = decision.route == "orchestrator" or OPEN_APP_FALLBACK in timings
    if not streamed or not ok:  # the orchestrator already spoke as it streamed
        speech.narrate(spoken)
    if decision.route == "fast" and not streamed:
        remember_turn(text, spoken)
    result = CommandResult(task_id, decision, spoken, ok, timings)
    _log_timing(text, result)
    events.emit(events.TaskEvent(task_id, "done" if ok else "failed", text, decision.route, spoken))
    return result


# --- Voice-loop task functions (§9.2 semantics; one task at a time until Phase 6) ---------


def start_task(
    command: str,
    pre_timings: dict[str, int] | None = None,
    on_done: Callable[[CommandResult], None] | None = None,
) -> threading.Thread:
    """Run `command` in the background so the listener keeps hearing "Zoya, stop"."""

    def run() -> None:
        result = handle_command(command, pre_timings)
        if on_done:
            on_done(result)

    worker = threading.Thread(target=run, name="zoya-task", daemon=True)
    worker.start()
    return worker


def stop_task() -> str:
    """Stop speech and the running task now (§11.3). Returns what to say."""
    _cancel.set()
    speech.cancel()
    return STOPPED_MESSAGE


def task_status() -> str:
    with _running_lock:
        commands = list(_running.values())
    return f"I'm working on: {commands[0]}." if commands else IDLE_MESSAGE


def _log_timing(text: str, result: CommandResult) -> None:
    record = {
        "at": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "task_id": result.task_id,
        "route": result.decision.route,
        "source": result.decision.source,
        "tool": result.decision.tool,
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
