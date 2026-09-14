"""document_agent (§9.5, Flow 7, STACK §9): makes, reads back, edits, opens and shares office files.

Strands primitives, not custom orchestration:
- A Strands `Agent` with its own prompt and narrow tools (zoya/tools/office.py, share_file,
  narrate), exposed to the brain with `Agent.as_tool(name, description, delegate=True)`
  (strands 1.55.1 agent/agent.py `as_tool`; agent/_agent_delegation.py): the brain's only call that
  turn, and the document agent's spoken read-back is the final answer, with no extra brain call.
- The parent's stop reaches it: `_AgentAsTool.stream` passes the parent's cancel signal on
  (agent/_agent_as_tool.py), and the parent is the task's orchestrator.
- Hooks as on every Zoya agent: TaskLimits (spend pooled with the task), StepTracker, and the
  ConfirmationGate last; SequentialToolExecutor so nothing runs while a confirmation waits.
- A fresh Agent per task: `_AgentAsTool` serialises calls to one agent ("already processing a
  request"), so two tasks each get their own instance. The tool name, description and schema are
  identical every time, so the brain's prompt prefix stays byte-stable for caching.

Docs: https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/
"""

from __future__ import annotations

import os
import time
from typing import Any

from strands import Agent
from strands.hooks import AfterInvocationEvent, BeforeInvocationEvent, HookProvider, HookRegistry
from strands.tools.executors import SequentialToolExecutor

from zoya import safety, tasks
from zoya.prompts import DOCUMENT_PROMPT
from zoya.tools.office import FILE_TOOLS
from zoya.tools.share import share_file

NAME = "document_agent"
MS_PER_S = 1000
DESCRIPTION = (
    "Make, read back, change, open or share a document: slides/presentation (pptx), Word document "
    "(docx), PDF, Markdown, Excel sheet (xlsx, with totals) or CSV, saved in ~/Documents/Zoya/. "
    "Also 'read slide 2', 'read row 3', 'make slide 3 shorter', 'open it', 'send it to my sister'. "
    "Input: the user's full request in plain words, plus the file path when it is about a file "
    "made earlier."
)


class UsageLog(HookProvider):
    """Per-stage latency and tokens for each document request (§13.5), in logs/timing.log."""

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.start)
        registry.add_callback(AfterInvocationEvent, self.log)

    def start(self, _event: BeforeInvocationEvent) -> None:
        self.started = time.monotonic()

    def log(self, event: AfterInvocationEvent) -> None:
        from zoya.tools.computer import log_stage

        metrics = event.agent.event_loop_metrics
        usage = metrics.accumulated_usage
        task = tasks.current()
        log_stage(
            NAME,
            task_id=task.id if task else "",
            document_ms=round(
                (time.monotonic() - getattr(self, "started", time.monotonic())) * MS_PER_S
            ),
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            cached_tokens=usage.get("cacheReadInputTokens", 0),
            model_calls=getattr(metrics, "cycle_count", 0),
        )


def build_document_agent() -> Agent:
    from zoya.models import get_model
    from zoya.orchestrator import TaskLimits, narrate_tool

    return Agent(
        name=NAME,
        description=DESCRIPTION,
        model=get_model("brain"),
        system_prompt=DOCUMENT_PROMPT,
        tools=[*FILE_TOOLS, share_file, narrate_tool],
        hooks=[
            TaskLimits(os.environ.get("BRAIN_MODEL", "")),
            UsageLog(),
            tasks.StepTracker(),
            safety.ConfirmationGate(),  # last: sees the final tool call
        ],
        tool_executor=SequentialToolExecutor(),
        callback_handler=None,
        trace_attributes={"zoya.component": NAME},
    )


def document_agent_tool() -> Any:
    """The brain's `document_agent` tool: a new sub-agent for each orchestrator (each task)."""
    return build_document_agent().as_tool(name=NAME, description=DESCRIPTION, delegate=True)
