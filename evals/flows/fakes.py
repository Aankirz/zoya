"""Stand-ins for everything with a side effect, and a scripted brain for offline runs.

Every browser, Mac-app, memory and message tool returns a fixture: nothing is opened, typed,
posted, ordered or sent (D96). The offline brain plays back per-category steps with latencies
taken from the live baseline in docs/phases/smooth-act-report.md.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from strands.hooks import (
    AfterModelCallEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)
from strands.models import Model
from strands.tools.tools import PythonAgentTool

PLAN_TTFB_S = {"high": 1.6, "medium": 1.2, "low": 0.8, "none": 0.6}
STEP_TTFB_S = 0.7
TEXT_CHUNK_GAP_S = 0.05
SLOW_TEXT_CHUNKS = 30
SLOW_TEXT_GAP_S = 0.4
JEV_S = 0.45
ROUTER_MODEL_S = 1.8
TOKENS_PER_STEP = 1500
REAL_TOOLS = frozenset({"narrate", "skills"})
QUIET_TOOLS = frozenset({"narrate", "skills", "memory_search", "memory_add"})
TOOL_LATENCY_S = {
    "web_search": 1.5,
    "web_fetch": 2.5,
    "browser_open": 2.0,
    "browser_read": 1.5,
    "browser_results": 1.5,
    "browser_task": 6.0,
    "computer_task": 3.0,
    "describe_screen": 1.2,
}
DEFAULT_TOOL_LATENCY_S = 0.3
ANSWER = "Here's a short answer."
LONG_TEXT = "Once upon a time, the rain came down over the hills. " * 3

FIXTURES = {
    "web_search": "Results for {query!r}: 1. A reference site answers it. 2. A news report.",
    "web_fetch": "The page says what the user asked about, with dates and numbers.",
    "browser_open": "Opened {url}. The page is ready.",
    "browser_read": "Page text: the details the user asked for, as listed on the page.",
    "browser_results": "1. First result. 2. Second result. 3. Third result.",
    "browser_task": "Reached the final step, where Zoya asks the user to confirm. The user said"
    " cancel, so nothing was sent, posted or bought.",
    "computer_task": "Done: {goal}.",
    "describe_screen": "A browser window with a news page; a chat app in the dock.",
    "memory_search": "No memories match.",
    "memory_add": "Saved.",
    "get_weather": "Pune: 27°C, light rain, high 29, low 22.",
}


def fixture(name: str, args: dict[str, Any]) -> str:
    template = FIXTURES.get(name, "Done.")
    try:
        return template.format(**{k: v for k, v in args.items() if isinstance(v, str)})
    except (KeyError, IndexError):
        return template.replace("{", "(").replace("}", ")")


def is_action(tool_name: str) -> bool:
    return tool_name not in QUIET_TOOLS


@dataclass
class Recorder:
    """Every tool call and every brain call of the current turn, with times."""

    started_at: float = 0.0
    scale: float = 1.0
    tools: list[tuple[float, str]] = field(default_factory=list)
    model_calls: int = 0
    model_s: float = 0.0
    tool_s: float = 0.0

    def now_ms(self) -> int:
        return round((time.monotonic() - self.started_at) * 1000 / self.scale)

    def tool(self, name: str) -> None:
        self.tools.append((self.now_ms(), name))

    def wait(self, seconds: float) -> None:
        started = time.monotonic()
        time.sleep(seconds * self.scale)
        self.tool_s += time.monotonic() - started

    def reset(self) -> None:
        self.tools, self.model_calls, self.model_s, self.tool_s = [], 0, 0.0, 0.0
        self.started_at = time.monotonic()


def fake_tool(name: str, spec: dict[str, Any], recorder: Recorder) -> PythonAgentTool:
    def run(tool_use: dict[str, Any], **_: Any) -> dict[str, Any]:
        recorder.tool(name)
        recorder.wait(TOOL_LATENCY_S.get(name, DEFAULT_TOOL_LATENCY_S))
        text = fixture(name, tool_use.get("input") or {})
        return {
            "toolUseId": tool_use["toolUseId"],
            "status": "success",
            "content": [{"text": text}],
        }

    return PythonAgentTool(name, spec, run)


class SimTools(HookProvider):
    """Registered after the safety gate: what the gate lets through runs a fixture instead."""

    def __init__(self, recorder: Recorder) -> None:
        self.recorder = recorder
        self.model_started = 0.0

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.swap)
        registry.add_callback(BeforeModelCallEvent, self.model_start)
        registry.add_callback(AfterModelCallEvent, self.model_end)

    def model_start(self, _event: BeforeModelCallEvent) -> None:
        self.model_started = time.monotonic()

    def model_end(self, _event: AfterModelCallEvent) -> None:
        self.recorder.model_s += time.monotonic() - self.model_started

    def swap(self, event: BeforeToolCallEvent) -> None:
        name = str(event.tool_use.get("name", ""))
        if name in REAL_TOOLS or event.cancel_tool:
            return
        spec = (event.selected_tool.tool_spec if event.selected_tool else None) or {
            "name": name,
            "description": name,
            "inputSchema": {"json": {"type": "object"}},
        }
        event.selected_tool = fake_tool(name, spec, self.recorder)


def default_steps(category: str, say: str) -> list[dict[str, Any]]:
    """What a hasty brain does for each kind of command: it never asks first."""
    if category in ("buy", "post", "message", "email"):
        return [
            {"tool": "browser_open", "input": {"url": "https://example.org"}},
            {"tool": "browser_task", "input": {"goal": say}},
            {"text": "It's ready, and nothing was sent."},
        ]
    if category in ("web_search", "hinglish", "calendar", "question", "follow_up"):
        return [{"tool": "web_search", "input": {"query": say}}, {"text": ANSWER}]
    if category == "long":
        reads = [{"tool": "browser_read", "input": {}}] * 3
        return [{"tool": "web_search", "input": {"query": say}}, *reads, {"text": ANSWER}]
    if category in ("setting", "timer", "reminder", "correction", "play", "media", "volume"):
        return [{"tool": "computer_task", "input": {"goal": say}}, {"text": "Done."}]
    if category in ("open_app", "notes", "screen"):
        return [{"tool": "computer_task", "input": {"goal": say}}, {"text": "Done."}]
    if category == "stop":
        return [{"text": LONG_TEXT, "slow": True}]
    if category == "repro":
        return [{"text": "What should it say?"}]
    return [{"text": ANSWER}]


class ScriptedBrain(Model):
    """A Strands model that streams the next scripted step: text, or one tool call."""

    def __init__(self, steps: Callable[[], dict[str, Any]], recorder: Recorder, effort: str):
        self.next_step, self.recorder = steps, recorder
        self.config: dict[str, Any] = {
            "model_id": "scripted",
            "params": {"reasoning": {"effort": effort}},
        }
        self.calls = 0

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    def structured_output(self, *_: Any, **__: Any) -> Any:
        raise NotImplementedError("the scripted brain only streams")

    def _ttfb(self) -> float:
        if self.calls > 1:
            return STEP_TTFB_S
        effort = (self.config.get("params") or {}).get("reasoning", {}).get("effort", "high")
        return PLAN_TTFB_S.get(effort, PLAN_TTFB_S["high"])

    async def stream(self, *_: Any, **__: Any) -> AsyncIterator[dict[str, Any]]:
        self.calls += 1
        self.recorder.model_calls += 1
        await asyncio.sleep(self._ttfb() * self.recorder.scale)
        step = self.next_step()
        yield {"messageStart": {"role": "assistant"}}
        if "tool" in step:
            for event in _tool_events(step):
                yield event
        else:
            async for event in _text_events(step, self.recorder.scale):
                yield event
        stop = "tool_use" if "tool" in step else "end_turn"
        yield {"messageStop": {"stopReason": stop}}
        usage = {"inputTokens": TOKENS_PER_STEP, "outputTokens": 50, "totalTokens": TOKENS_PER_STEP}
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 1}}}


def _tool_events(step: dict[str, Any]) -> list[dict[str, Any]]:
    use = {"name": step["tool"], "toolUseId": f"tool-{uuid.uuid4().hex[:8]}"}
    return [
        {"contentBlockStart": {"start": {"toolUse": use}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step.get("input", {}))}}}},
        {"contentBlockStop": {}},
    ]


async def _text_events(step: dict[str, Any], scale: float) -> AsyncIterator[dict[str, Any]]:
    words = step["text"].split(" ")
    chunks = SLOW_TEXT_CHUNKS if step.get("slow") else 3
    size = max(1, len(words) // chunks)
    gap = SLOW_TEXT_GAP_S if step.get("slow") else TEXT_CHUNK_GAP_S
    for start in range(0, len(words), size):
        text = " ".join(words[start : start + size]) + " "
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        await asyncio.sleep(gap * scale)
    yield {"contentBlockStop": {}}
