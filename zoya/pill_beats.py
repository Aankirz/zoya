"""What the pill shows for each sound, and the one-way doors (D152): no AppKit, so it is tested.

Every earcon is punctuation for one visual change. A sound that changes Zoya's state moves the
pill to that state; a sound inside a state (a tick, a saved memory, a warning before the ask)
gets a beat, one blink of the eyes. Nothing makes a sound without something to see.

After an ask is confirmed or cancelled, or its task has ended, a late or repeated "waiting" for
that ask is dropped: the pill never goes back to asking for the same action.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

STATE_EARCONS = {
    "listening": "listening",
    "heard": "thinking",
    "working": "thinking",
    "error": "error",
    "blocked": "error",
    "stop": "stopped",
    "cancel": "stopped",
}
BEAT_EARCONS = frozenset(
    {
        "success",
        "attention",
        "warning",
        "progress-step",
        "add-to-cart",
        "purchase",
        "checkpoint",
        "queued",
        "complete",
    }
)
DECIDED_STATES = {"confirm": "thinking", "cancel": "stopped", "timeout": "stopped"}
ENDED_TASKS = frozenset({"done", "failed", "cancelled"})
ASK_KEY_CHARS = 12


def earcon_message(kind: str) -> dict[str, Any] | None:
    if kind in STATE_EARCONS:
        return {"k": "state", "state": STATE_EARCONS[kind], "sound": kind}
    if kind in BEAT_EARCONS:
        return {"k": "beat", "sound": kind}
    return None


def ask_key(task_id: str, summary: str) -> str:
    """Names one ask without sending its words: the summary may hold an amount or an address."""
    digest = hashlib.sha256(f"{task_id}\n{summary}".encode()).hexdigest()
    return f"{task_id}:{digest[:ASK_KEY_CHARS]}"


@dataclass
class Doors:
    decided: set[str] = field(default_factory=set)
    ended: set[str] = field(default_factory=set)

    def admit(self, message: dict[str, Any]) -> bool:
        """False for a message that would re-open a closed ask; records the closing ones."""
        if message.get("decided"):
            self.decided.add(str(message["decided"]))
        if message.get("ended"):
            self.ended.add(str(message["ended"]))
        ask = message.get("ask")
        if message.get("state") != "waiting" or not ask:
            return True
        task = str(ask).split(":", 1)[0]
        return ask not in self.decided and task not in self.ended
