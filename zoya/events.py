"""Shared event contract (Phase 1 "Contracts first").

Other phases build against these names and payloads: the audio engine
(Phase 2) subscribes to EARCON/NARRATE, the safety gate (Phase 3) to
CONFIRMATION, the Task Manager (Phase 6) to TASK, the overlay (Phase 7) to
OVERLAY. Payloads are frozen dataclasses; add fields append-only with defaults.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)

NARRATE = "narrate"
EARCON = "earcon"
TASK = "task"
CONFIRMATION = "confirmation"
OVERLAY = "overlay"

EarconKind = Literal[
    "listening", "heard", "working", "success", "error", "attention", "stop", "warning", "cancel"
]
TaskStatus = Literal["started", "running", "done", "failed", "cancelled"]
Route = Literal["fast", "orchestrator", "stop"]


@dataclass(frozen=True)
class NarrateEvent:
    text: str
    name: str = NARRATE


@dataclass(frozen=True)
class EarconEvent:
    kind: EarconKind
    name: str = EARCON


@dataclass(frozen=True)
class TaskEvent:
    task_id: str
    status: TaskStatus
    command: str
    route: Route
    detail: str = ""
    name: str = TASK


@dataclass(frozen=True)
class ConfirmationEvent:
    task_id: str
    summary: str
    decision: Literal["pending", "confirm", "cancel", "timeout"] = "pending"
    name: str = CONFIRMATION


@dataclass(frozen=True)
class OverlayEvent:
    text: str
    state: Literal["idle", "listening", "working", "speaking"] = "idle"
    extra: dict[str, str] = field(default_factory=dict)
    name: str = OVERLAY


Event = NarrateEvent | EarconEvent | TaskEvent | ConfirmationEvent | OverlayEvent

_subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)


def subscribe(name: str, handler: Callable[[Event], None]) -> None:
    _subscribers[name].append(handler)


def emit(event: Event) -> None:
    """Deliver synchronously; a failing subscriber is logged and never breaks the caller."""
    for handler in _subscribers[event.name]:
        try:
            handler(event)
        except Exception:  # noqa: BLE001 — one bad listener must not stop a task
            log.exception("event handler failed for %s", event.name)
