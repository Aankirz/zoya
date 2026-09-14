"""Result TTL cache (harness §4 "Results cache"): repeated lookups cost 0 network and 0 tokens.

Only read-only work is cached: `get` and `put` refuse any name the safety registry doesn't list as
free, or whose name touches money, sending, posting or deleting. A cached "Subscribed" or "Order
placed" would be a lie, and a cached action would skip its confirmation.
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from zoya import safety
from zoya.config import RESULT_CACHE_MAX_ITEMS

NEVER_CACHE = re.compile(
    r"order|pay|buy|cart|checkout|send|post|comment|subscribe|like|delete|remove|click|type|memory"
)

_lock = threading.Lock()
_items: OrderedDict[tuple[str, str], tuple[float, Any]] = OrderedDict()
_now: Callable[[], float] = time.monotonic


def cacheable(name: str) -> bool:
    return safety.risk_of(name) == "free" and not NEVER_CACHE.search(name)


def _key(name: str, args: dict[str, Any]) -> tuple[str, str]:
    return name, repr(sorted((k, " ".join(str(v).casefold().split())) for k, v in args.items()))


def get(name: str, args: dict[str, Any]) -> Any | None:
    if not cacheable(name):
        return None
    with _lock:
        hit = _items.get(_key(name, args))
        if hit is None or _now() >= hit[0]:
            return None
        return hit[1]


def put(name: str, args: dict[str, Any], value: Any, ttl_s: float) -> None:
    if not cacheable(name) or ttl_s <= 0:
        return
    with _lock:
        _items[_key(name, args)] = (_now() + ttl_s, value)
        _items.move_to_end(_key(name, args))
        while len(_items) > RESULT_CACHE_MAX_ITEMS:
            _items.popitem(last=False)


def clear() -> None:
    with _lock:
        _items.clear()
