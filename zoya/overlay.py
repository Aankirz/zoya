"""Stage overlay (Phase 7, §9.11): Zoya's "presence", live captions and an action ring, for
sighted judges only. The blind user and the agent never depend on it.

Two halves:
- In Zoya (`start`): subscribes to zoya/events.py (the only source of overlay state), masks
  secrets, and writes one JSON line per update to a child process. Never blocks: a full queue
  drops the update.
- The child (`python -m zoya.overlay`): an AppKit accessory app with a non-activating,
  click-through NSPanel. A separate process keeps AppKit and the GIL off the voice path, and an
  overlay crash can't stop Zoya. Screen captures exclude its pid (screen.own_pids, D23/AUDIT B11).

Avatar: a Core Animation orb + SF Symbol per state. Plane's Agent Avatar Lab needs an account,
so no generated art (assets/avatars stays empty).

APIs (verified 2026-09-14 on macOS 26.6.2, pyobjc 12.2.2):
- https://developer.apple.com/documentation/appkit/nspanel
- https://developer.apple.com/documentation/appkit/nswindow/stylemask-swift.struct/nonactivatingpanel
- https://developer.apple.com/documentation/appkit/nswindow/ignoresmouseevents
- https://developer.apple.com/documentation/appkit/nswindow/canbecomekey
- https://developer.apple.com/documentation/appkit/nsglasseffectview (macOS 26)
- https://developer.apple.com/documentation/appkit/nsvisualeffectview/material-swift.enum/hudwindow
- https://developer.apple.com/documentation/appkit/nsworkspace/accessibilitydisplayshouldreducemotion
- https://developer.apple.com/documentation/appkit/nsimage/init(systemsymbolname:accessibilitydescription:)
- https://developer.apple.com/design/human-interface-guidelines/materials , /motion , /accessibility
- https://pyobjc.readthedocs.io/en/latest/api/module-PyObjCTools.AppHelper.html (callAfter)
"""

from __future__ import annotations

import contextlib
import json
import queue
import subprocess
import sys
import threading
import time
from typing import Any

from zoya import events
from zoya.config import LOG_DIR

OVERLAY_LOG = LOG_DIR / "overlay.log"
QUEUE_MAX = 64  # updates waiting for the pipe; beyond this the overlay is stuck, so drop
RING_LEAD_S = 0.25  # the ring is on screen this long before the click lands
RING_PAD_PT = 8.0
POINT_RING_PT = 44.0  # a pixel click has no element frame: a ring this big around the point
CAPTION_MAX_CHARS = 160
HIDDEN_CAPTION = "(private — hidden)"
ERROR_KINDS = {"error", "blocked"}
STOP_KINDS = {"stop", "cancel"}

_child: subprocess.Popen | None = None
_queue: queue.Queue[str] = queue.Queue(QUEUE_MAX)


# --- In Zoya: events → masked messages ---------------------------------------------------------


def caption_text(text: str) -> str:
    """What a caption may show. Anything that looks like an OTP, password, PIN or card is hidden
    whole (the Phase 4 memory filter errs toward refusing); numbers are redacted on top."""
    from zoya import safety
    from zoya.tools.memory import secret_reason

    clean = " ".join(text.split())
    if secret_reason(clean):
        return HIDDEN_CAPTION
    clean = safety.redact(clean)
    return clean if len(clean) <= CAPTION_MAX_CHARS else clean[: CAPTION_MAX_CHARS - 1] + "…"


def running() -> bool:
    return _child is not None and _child.poll() is None


def pids() -> set[int]:
    """The overlay's pid while it runs: every screen capture leaves its windows out."""
    return {_child.pid} if running() and _child is not None else set()


def _send(message: dict[str, Any]) -> None:
    if not running():
        return
    message["t"] = time.time()
    with contextlib.suppress(queue.Full):  # a stuck overlay loses updates; Zoya never waits
        _queue.put_nowait(json.dumps(message, ensure_ascii=False))


def _task_name(task_id: str) -> str:
    from zoya import tasks

    live = tasks.running()
    match = next((t for t in live if t.id == task_id), None)
    return match.spoken_name() if match and len(live) > 1 else ""


def _on_event(event: events.Event) -> None:
    message = to_message(event)
    if message:
        _send(message)


def to_message(event: events.Event) -> dict[str, Any] | None:
    """One overlay update for an event, captions masked here so secrets never cross the pipe."""
    if isinstance(event, events.NarrateEvent):
        return {"k": "zoya", "text": caption_text(event.text)}
    if isinstance(event, events.EarconEvent):
        state = {"listening": "listening", "working": "thinking"}.get(event.kind)
        state = state or ("error" if event.kind in ERROR_KINDS else None)
        state = state or ("stopped" if event.kind in STOP_KINDS else None)
        return {"k": "state", "state": state} if state else None
    if isinstance(event, events.TaskEvent):
        state = {"started": "thinking", "done": "idle", "failed": "error", "cancelled": "stopped"}
        return {"k": "state", "state": state[event.status]} if event.status in state else None
    if isinstance(event, events.ConfirmationEvent):
        if event.decision == "pending":
            return {"k": "state", "state": "waiting", "task": _task_name(event.task_id)}
        return {"k": "state", "state": "thinking"}
    if isinstance(event, events.OverlayEvent):
        return _overlay_message(event)
    return None


def _overlay_message(event: events.OverlayEvent) -> dict[str, Any] | None:
    extra = event.extra
    if extra.get("role") == "user":
        return {"k": "user", "text": caption_text(event.text)}
    if "ring" in extra:
        return {"k": "ring", "rect": [float(v) for v in extra["ring"].split(",")]}
    if extra.get("speech") == "done":
        return {"k": "speech_done"}
    state = "acting" if extra.get("tool") else "thinking"
    step = caption_text(extra.get("tool") or event.text)
    return {"k": "state", "state": state, "step": step, "task": extra.get("task", "")}


def show_ring(x: float, y: float, width: float = 0.0, height: float = 0.0) -> None:
    """Ring the target (global points, top-left origin) just before a click. Call only AFTER the
    screenshot/OCR evidence for this step was captured."""
    if not running():
        return
    if width <= 0 or height <= 0:
        x, y = x - POINT_RING_PT / 2, y - POINT_RING_PT / 2
        width = height = POINT_RING_PT
    ring = (
        f"{x - RING_PAD_PT},{y - RING_PAD_PT},{width + 2 * RING_PAD_PT},{height + 2 * RING_PAD_PT}"
    )
    events.emit(events.OverlayEvent("", "working", {"ring": ring}))
    time.sleep(RING_LEAD_S)


def _write_loop(child: subprocess.Popen) -> None:
    while child.poll() is None:
        line = _queue.get()
        try:
            child.stdin.write(line + "\n")
            child.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return


def start() -> str:
    """Launch the overlay and subscribe it to Zoya's events."""
    global _child
    if running():
        return "on"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stderr = OVERLAY_LOG.open("a", encoding="utf-8")
    _child = subprocess.Popen(
        [sys.executable, "-m", "zoya.overlay"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=stderr,
        text=True,
    )
    threading.Thread(target=_write_loop, args=(_child,), name="zoya-overlay", daemon=True).start()
    for name in (events.NARRATE, events.EARCON, events.TASK, events.CONFIRMATION, events.OVERLAY):
        events.subscribe(name, _on_event)
    return f"on (pid {_child.pid}, log {OVERLAY_LOG})"


if __name__ == "__main__":
    from zoya.overlay_app import run

    sys.exit(run())
