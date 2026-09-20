"""Spend Jev's latency while the user is still speaking (D82).

Phase A measured Jev at ~500–600 ms p50 with a ~430 ms round-trip floor that no
batching or state-size tuning recovers. The only way a rule miss routes in under
300 ms is to have routed it already: partial transcripts during the utterance
start the route, and end-of-speech collects an answer that is usually waiting.

Preparation is a routing decision and nothing else — read-only, invisible, and
free to throw away. `commit` hands it over only when the final transcript says
the same thing as the partial it was prepared from; anything else is discarded
and the caller routes normally.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time

from zoya.config import SPECULATION_TTL_S, SPECULATION_WAIT_S
from zoya.router import RouteDecision, clean_command, route

log = logging.getLogger(__name__)


MS_PER_S = 1000


@dataclasses.dataclass
class _Preparation:
    text: str
    started_at: float
    ready: threading.Event = dataclasses.field(default_factory=threading.Event)
    decision: RouteDecision | None = None
    prepared_ms: int = 0


_lock = threading.Lock()
_current: _Preparation | None = None


def _key(text: str) -> str:
    return clean_command(text).casefold()


def prepare(text: str) -> bool:
    """Start routing a partial transcript. Repeats of the same words cost nothing, and say so:
    False means no route was started, so the caller's budget is untouched."""
    global _current
    if not _key(text):
        return False
    with _lock:
        if _current is not None and _key(_current.text) == _key(text):
            return False
        preparation = _Preparation(text, time.monotonic())
        _current = preparation
    threading.Thread(target=_run, args=(preparation,), daemon=True).start()
    return True


def _run(preparation: _Preparation) -> None:
    try:
        preparation.decision = route(preparation.text)
    except Exception as error:  # noqa: BLE001 — speculation may never break the voice loop
        log.warning("speculative route failed (%s)", type(error).__name__)
    finally:
        preparation.prepared_ms = round((time.monotonic() - preparation.started_at) * MS_PER_S)
        preparation.ready.set()


def discard() -> None:
    global _current
    with _lock:
        _current = None


def peek(text: str) -> RouteDecision | None:
    """The prepared route for these words, leaving it in place for `commit`."""
    return _prepared(_current, text)


def commit(text: str) -> RouteDecision | None:
    """The prepared route, if it was prepared for these words. None means route normally."""
    global _current
    with _lock:
        preparation, _current = _current, None
    return _prepared(preparation, text)


def _prepared(preparation: _Preparation | None, text: str) -> RouteDecision | None:
    if preparation is None or _key(preparation.text) != _key(text):
        return None
    if time.monotonic() - preparation.started_at > SPECULATION_TTL_S:
        return None
    if not preparation.ready.wait(SPECULATION_WAIT_S):
        return None
    decision = preparation.decision
    if decision is None:
        return None
    translated = "translate_ms" in decision.timings_ms
    if translated and preparation.text != text:
        return None
    timings = {**decision.timings_ms, "speculated_ms": preparation.prepared_ms}
    return dataclasses.replace(
        decision, text=decision.text if translated else text, timings_ms=timings
    )
