"""Tool registration convention (Phase 1 "Contracts first").

Each module in zoya/tools and zoya/agents exposes a module-level `TOOLS` list of
Strands tools; the orchestrator collects them with `collect_tools()`. Tools
return a short sentence Zoya can speak, and raise `ToolError` with a polite,
speakable message when they fail.
"""

from __future__ import annotations

import contextvars
import importlib
import pkgutil
import threading
from typing import Any

ABANDONED_MESSAGE = "That step ran out of time, so I stopped it."


class ToolError(Exception):
    """A tool failure whose message is safe and polite to say out loud."""


_abandoned: contextvars.ContextVar[threading.Event | None] = contextvars.ContextVar(
    "zoya_abandoned_action", default=None
)


def watch_abandon(flag: threading.Event) -> None:
    """Called inside a skill action's own context: once `flag` is set, its next step refuses."""
    _abandoned.set(flag)


def check_abandoned() -> None:
    flag = _abandoned.get()
    if flag is not None and flag.is_set():
        raise ToolError(ABANDONED_MESSAGE)


def collect_tools(*packages: str) -> list[Any]:
    tools: list[Any] = []
    for package_name in packages:
        package = importlib.import_module(package_name)
        # Sorted: the tool list must be byte-identical across calls so OpenAI can cache the prefix.
        for module_info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            tools.extend(getattr(module, "TOOLS", []))
    return tools
