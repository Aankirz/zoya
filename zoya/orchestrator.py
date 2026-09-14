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
import time
import uuid
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


# --- Orchestrator -----------------------------------------------------------------


@tool(name="narrate")
def narrate_tool(text: str) -> str:
    """Say a short progress update (under 12 words) to the user out loud."""
    speech.narrate(text)
    return "Said."


def build_orchestrator(cost_cap_usd: float = PER_TASK_COST_CAP_USD) -> Agent:
    """A fresh Agent per task (AUDIT B6: one Agent can't run two calls at once)."""
    from zoya.models import get_model

    tools = [*collect_tools("zoya.tools", "zoya.agents"), narrate_tool]
    limits = TaskLimits(os.environ.get("BRAIN_MODEL", ""), cost_cap_usd)
    return Agent(
        model=get_model("brain"),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=tools,
        hooks=[limits],
        trace_attributes={"zoya.component": "orchestrator"},
    )


def run_orchestrator(command: str) -> str:
    """Stream the brain's answer to stdout and return the sentence to speak."""
    try:
        result = build_orchestrator()(command)
    except TaskLimitExceeded as limit:
        log.warning("task stopped: %s", limit)
        return LIMIT_MESSAGE
    return str(result).strip() or "Done."


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
            return run_fast_tool(decision), True
        return run_orchestrator(decision.text), True
    except ToolError as error:
        return str(error), False
    except KeyboardInterrupt:
        return STOPPED_MESSAGE, False
    except Exception:  # noqa: BLE001 — never crash on a command; say so politely
        log.exception("command failed")
        return GENERIC_FAILURE, False
    finally:
        timings[stage] = round((time.monotonic() - started) * MS_PER_S)


def handle_command(text: str) -> CommandResult:
    task_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    with trace.get_tracer("zoya").start_as_current_span("zoya.command") as span:
        decision = route(text)
        timings = dict(decision.timings_ms)
        events.emit(events.TaskEvent(task_id, "started", text, decision.route))
        spoken, ok = _execute(decision, timings)
        # Fast path target is router + tool (Done-when #2); speech is queued, not waited on.
        timings["total_ms"] = round((time.monotonic() - started) * MS_PER_S)
        span.set_attributes({f"zoya.{k}": v for k, v in timings.items()})
        span.set_attributes({"zoya.route": decision.route, "zoya.tool": decision.tool or ""})
    speech.narrate(spoken)
    result = CommandResult(task_id, decision, spoken, ok, timings)
    _log_timing(text, result)
    events.emit(events.TaskEvent(task_id, "done" if ok else "failed", text, decision.route, spoken))
    return result


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
