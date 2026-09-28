"""The Hub page's only door into Zoya: a fixed list of checked commands (D119)."""

from __future__ import annotations

import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from zoya import config

PAGES = frozenset({"today", "history", "memory", "plan", "setup", "voice"})
PANES = frozenset({"microphone", "accessibility", "screen", "automation"})
PILL_POSITIONS = frozenset({"bottom", "left", "right", "notch"})
HOTKEYS = frozenset(config.HOTKEYS)
MEMORY_ID = re.compile(r"[0-9a-f]{32}")
MESSAGE_KEYS = frozenset({"cmd", "id", "args"})
OPEN_HUB_NOTICE = "app.zoya.Zoya.openHub"
CLEAR_TOKEN_TTL_S = 120.0
ASK_MAX_CHARS = 500
UNSAFE_CHAR = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2066-\u2069\ufeff]")
TOKEN_BYTES = 16


def _one_of(allowed: frozenset[str]) -> Callable[[object], bool]:
    return lambda value: isinstance(value, str) and value in allowed


def _boolean(value: object) -> bool:
    return isinstance(value, bool)


SETTINGS: dict[str, Callable[[object], bool]] = {
    "largerText": _boolean,
    "easierLetters": _boolean,
    "launchAtLogin": _boolean,
    "pillPosition": _one_of(PILL_POSITIONS),
    "hotkey": _one_of(HOTKEYS),
}


def _memory_id(value: object) -> bool:
    return isinstance(value, str) and MEMORY_ID.fullmatch(value) is not None


def ask_text(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > ASK_MAX_CHARS or UNSAFE_CHAR.search(value):
        return None
    return value.strip() or None


def _setting(args: dict[str, Any]) -> bool:
    check = SETTINGS.get(args.get("key")) if isinstance(args.get("key"), str) else None
    return check is not None and check(args.get("value"))


ARGUMENTS: dict[str, dict[str, Callable[[object], bool]]] = {
    "getPage": {"page": _one_of(PAGES)},
    "deleteMemory": {"memory": _memory_id},
    "openPermissionPane": {"pane": _one_of(PANES)},
    "checkForUpdates": {},
    "sendProblemReport": {},
    "setSetting": {"key": lambda _key: True, "value": lambda _value: True},
    "prepareClearHistory": {},
    "clearHistory": {"token": _memory_id},
    "pageState": {"page": _one_of(PAGES)},
    "ask": {"text": lambda value: ask_text(value) is not None},
}
WHOLE_CHECKS: dict[str, Callable[[dict[str, Any]], bool]] = {"setSetting": _setting}


@dataclass(frozen=True)
class Command:
    name: str
    request_id: int
    args: dict[str, Any]


def _request_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def parse(body: object) -> Command | None:
    if not isinstance(body, dict) or set(body) != MESSAGE_KEYS:
        return None
    name, args = body["cmd"], body["args"]
    spec = ARGUMENTS.get(name) if isinstance(name, str) else None
    if spec is None or not isinstance(args, dict) or set(args) != set(spec):
        return None
    if not _request_id(body["id"]) or not all(check(args[key]) for key, check in spec.items()):
        return None
    whole = WHOLE_CHECKS.get(name)
    if whole is not None and not whole(args):
        return None
    return Command(name, body["id"], dict(args))


class ClearGuard:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.token = ""
        self.issued_at = 0.0

    def issue(self) -> str:
        self.token, self.issued_at = secrets.token_hex(TOKEN_BYTES), self.clock()
        return self.token

    def redeem(self, token: str) -> bool:
        fresh = self.clock() - self.issued_at <= CLEAR_TOKEN_TTL_S
        valid = bool(self.token) and fresh and secrets.compare_digest(token, self.token)
        self.token = "" if valid else self.token
        return valid
