"""Action recipes (harness §4 "graph"): per site and intent, the strategy that last worked is
tried first next time; the others remain the fallback, so a changed page re-derives on its own.

Stagehand's action cache stores the resolved selector for an instruction and replays it with no
LLM call, running the normal path on a miss (https://docs.stagehand.dev/v3/best-practices/caching,
https://browserbase.com/blog/stagehand-caching/). Zoya's recipes are code, so what is cached is
which recipe strategy (a selector path) resolved the button, keyed by host + intent.

Never cached: paying, ordering, checkout, confirming or signing in. Those steps always run their
full path and the safety gate, so a stale recipe can never skip or reorder a confirmation.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Sequence
from typing import Any

from zoya.config import LOG_DIR

RECIPES_FILE = LOG_DIR / "recipes.json"
NEVER_RECIPE = re.compile(r"pay|order|buy|checkout|confirm|sign.?in|log.?in|password|otp", re.I)

_lock = threading.Lock()


def recordable(intent: str) -> bool:
    return bool(intent.strip()) and not NEVER_RECIPE.search(intent)


def _key(host: str, intent: str) -> str:
    return f"{host.casefold().strip()} {' '.join(intent.casefold().split())}"


def _load() -> dict[str, str]:
    try:
        return json.loads(RECIPES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ordered(host: str, intent: str, strategies: Sequence[str]) -> list[str]:
    """`strategies` with the one that last worked for this host + intent first."""
    best = _load().get(_key(host, intent)) if recordable(intent) else None
    return sorted(strategies, key=lambda name: name != best)


def record(host: str, intent: str, strategy: str) -> None:
    if not recordable(intent):
        return
    with _lock:
        recipes = _load()
        if recipes.get(_key(host, intent)) == strategy:
            return
        recipes[_key(host, intent)] = strategy
        try:
            RECIPES_FILE.parent.mkdir(exist_ok=True)
            RECIPES_FILE.write_text(json.dumps(recipes, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # a lost recipe only costs the fallback order next time


def first_found(
    host: str, intent: str, strategies: dict[str, Callable[[], Any]]
) -> tuple[str, Any]:
    """Run strategies (last winner first) until one returns an element; record the winner.
    A strategy returns None when it doesn't apply; its own errors propagate."""
    for name in ordered(host, intent, list(strategies)):
        if (found := strategies[name]()) is not None:
            record(host, intent, name)
            return name, found
    return "", None
