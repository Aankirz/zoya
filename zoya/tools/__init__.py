"""Tool registration convention (Phase 1 "Contracts first").

Each module in zoya/tools and zoya/agents exposes a module-level `TOOLS` list of
Strands tools; the orchestrator collects them with `collect_tools()`. Tools
return a short sentence Zoya can speak, and raise `ToolError` with a polite,
speakable message when they fail.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any


class ToolError(Exception):
    """A tool failure whose message is safe and polite to say out loud."""


def collect_tools(*packages: str) -> list[Any]:
    tools: list[Any] = []
    for package_name in packages:
        package = importlib.import_module(package_name)
        # Sorted: the tool list must be byte-identical across calls so OpenAI can cache the prefix.
        for module_info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            tools.extend(getattr(module, "TOOLS", []))
    return tools
