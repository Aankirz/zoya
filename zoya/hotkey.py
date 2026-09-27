"""fn+Shift, heard the instant it goes down: a listen-only event tap on modifier changes (D125)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

MASK_NAMES = {
    "fn": "kCGEventFlagMaskSecondaryFn",
    "shift": "kCGEventFlagMaskShift",
    "control": "kCGEventFlagMaskControl",
    "option": "kCGEventFlagMaskAlternate",
    "command": "kCGEventFlagMaskCommand",
}


def wanted_mask(keys: tuple[str, ...]) -> int:
    import Quartz

    mask = 0
    for key in keys:
        mask |= getattr(Quartz, MASK_NAMES[key])
    return mask


def held_now(keys: tuple[str, ...]) -> bool:
    import Quartz

    wanted = wanted_mask(keys)
    return (
        Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateHIDSystemState) & wanted == wanted
    )


class Watcher:
    def __init__(self, keys: tuple[str, ...], on_down: Callable[[int], None]) -> None:
        self.keys = keys
        self.wanted = wanted_mask(keys)
        self.on_down = on_down
        self.held = False
        self.down_at = 0.0
        self.live = False
        self.tap: Any = None

    def start(self) -> bool:
        ready = threading.Event()
        threading.Thread(target=self._run, args=(ready,), name="zoya-hotkey", daemon=True).start()
        ready.wait(timeout=2.0)
        log.info("push-to-talk keys: %s", "event tap" if self.live else "polled")
        return self.live

    def _run(self, ready: threading.Event) -> None:
        import Quartz

        mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        self.tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self._event,
            None,
        )
        if self.tap is None:
            ready.set()
            return
        source = Quartz.CFMachPortCreateRunLoopSource(None, self.tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(self.tap, True)
        self.live = True
        ready.set()
        Quartz.CFRunLoopRun()

    def _event(self, _proxy: Any, kind: int, event: Any, _refcon: Any) -> Any:
        import Quartz

        if kind in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
            Quartz.CGEventTapEnable(self.tap, True)
            return event
        held = Quartz.CGEventGetFlags(event) & self.wanted == self.wanted
        if held and not self.held:
            self.down_at = time.monotonic()
            self.held = True
            self.on_down(Quartz.CGEventGetTimestamp(event))
        elif not held:
            self.held = False
        return event

    def is_held(self) -> bool:
        return self.held if self.live else held_now(self.keys)
