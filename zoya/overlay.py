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
from collections.abc import Callable
from typing import Any

from zoya import events
from zoya.config import LOG_DIR

OVERLAY_LOG = LOG_DIR / "overlay.log"
QUEUE_MAX = 64  # updates waiting for the pipe; beyond this the overlay is stuck, so drop
RING_LEAD_S = 0.25  # the ring is on screen this long before the click lands
RING_PAD_PT = 8.0
POINT_RING_PT = 44.0  # a pixel click has no element frame: a ring this big around the point
CAPTION_MAX_CHARS = 160
HIDDEN_CAPTION = "Hidden for privacy"
# Tool names → what a judge reads on the stage label; anything unlisted is sentence-cased.
TOOL_VERBS = {
    "amazon add to cart": "Adding to cart",
    "amazon cart": "Checking the cart",
    "amazon checkout": "Checking out",
    "amazon place order": "Placing the order",
    "amazon search": "Searching Amazon",
    "ax press": "Pressing a button",
    "ax read": "Reading the app",
    "browser click": "Clicking",
    "browser open": "Opening a page",
    "browser read": "Reading the page",
    "browser screenshot": "Looking at the page",
    "browser type": "Typing",
    "click": "Clicking",
    "computer task": "Using the Mac",
    "create document": "Writing a document",
    "describe screen": "Looking at the screen",
    "document agent": "Working on a document",
    "key": "Pressing keys",
    "memory add": "Remembering",
    "memory search": "Recalling",
    "open app": "Opening an app",
    "read document": "Reading a document",
    "read screen text": "Reading the screen",
    "screenshot": "Looking at the screen",
    "scroll": "Scrolling",
    "set reminder": "Setting a reminder",
    "share file": "Sharing a file",
    "spotify play song": "Playing music",
    "type text": "Typing",
    "web fetch": "Reading a website",
    "web search": "Searching the web",
    "youtube play video": "Playing a video",
    "youtube search": "Searching YouTube",
}
ERROR_KINDS = {"error", "blocked"}
STAKE_PREFIX = "I'm about to "
LEVEL_EVERY_S = 0.08
LEVEL_GAIN = 12.0
STOP_KINDS = {"stop", "cancel"}
CHIP_MAX_CHARS = 24
CHIP_SEPARATOR = "\n"
CHIP_ARGS = ("app_name", "app", "query", "title", "note_name", "url", "song", "item", "city")

_child: subprocess.Popen | None = None
_last_level = 0.0
_presence = False
_ask_handler: Callable[[str], None] | None = None
CONTROLS_ONLY_ARG = "--controls-only"
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


def _alive() -> bool:
    return _child is not None and _child.poll() is None


def running() -> bool:
    """The stage presence is showing (not just the menu-bar controls)."""
    return _presence and _alive()


def pids() -> set[int]:
    """The overlay's pid while it runs: every screen capture leaves its windows out."""
    return {_child.pid} if _alive() and _child is not None else set()


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
            stake = caption_text(stake_line(event.summary))
            return {
                "k": "state",
                "state": "waiting",
                "task": _task_name(event.task_id),
                "stake": stake,
            }
        return {"k": "state", "state": "thinking"}
    if isinstance(event, events.OverlayEvent):
        return _overlay_message(event)
    return None


def stake_line(summary: str) -> str:
    text = " ".join(summary.split()).removesuffix(".")
    if not text.startswith(STAKE_PREFIX):
        return text
    text = text.removeprefix(STAKE_PREFIX).replace(" total ", ", ")
    return text[:1].upper() + text[1:]


def level(block: Any) -> None:
    global _last_level
    now = time.monotonic()
    if not running() or now - _last_level < LEVEL_EVERY_S:
        return
    _last_level = now
    rms = float((block * block).mean()) ** 0.5
    _send({"k": "level", "v": round(min(rms * LEVEL_GAIN, 1.0), 3)})


def _overlay_message(event: events.OverlayEvent) -> dict[str, Any] | None:
    extra = event.extra
    if extra.get("role") == "user":
        return {"k": "user", "text": caption_text(event.text)}
    if extra.get("role") == "intent":
        chips = [c for c in extra.get("chips", "").split(CHIP_SEPARATOR) if c]
        return {"k": "intent", "text": caption_text(event.text), "chips": chips}
    if "ring" in extra:
        return {"k": "ring", "rect": [float(v) for v in extra["ring"].split(",")]}
    if extra.get("speech") == "done":
        return {"k": "speech_done"}
    state = "acting" if extra.get("tool") else "thinking"
    step = caption_text(step_label(extra.get("tool") or event.text))
    tool = extra.get("tool", "")
    return {"k": "state", "state": state, "step": step, "task": extra.get("task", ""), "tool": tool}


def intent_chips(decision: Any) -> tuple[str, ...]:
    """What Zoya understood, from the route already prepared (D127): no model call of its own,
    and only words; nothing here runs anything."""
    if decision.route == "fast" and decision.tool:
        kind = step_label(decision.tool).lower()
    elif decision.route == "skill" and decision.skill:
        kind = decision.skill.removesuffix("_web").replace("_", " ")
    else:
        return ()
    noun = next((str(decision.args[k]) for k in CHIP_ARGS if decision.args.get(k)), "")
    chips = (kind, caption_text(noun).lower()) if noun else (kind,)
    return tuple(c if len(c) <= CHIP_MAX_CHARS else c[: CHIP_MAX_CHARS - 1] + "…" for c in chips)


def step_label(step: str) -> str:
    """ "using memory search" or "memory_search" → "Recalling"; unknown tools → "Get weather"."""
    name = step.removeprefix("using ").replace("_", " ").strip()
    return TOOL_VERBS.get(name, name[:1].upper() + name[1:])


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


def _forget(message: dict[str, Any]) -> None:
    from zoya import hub_bridge
    from zoya.tools import memory

    item, request = message.get("memory"), message.get("request")
    valid = hub_bridge._memory_id(item) and hub_bridge._request_id(request)
    if valid:
        send({"hub": {"id": request, "ok": memory.forget(item)}})


def on_ask(handler: Callable[[str], None]) -> None:
    global _ask_handler
    _ask_handler = handler


def _ask(message: dict[str, Any]) -> None:
    from zoya import hub_bridge

    text = hub_bridge.ask_text(message.get("text"))
    if text is not None and _ask_handler is not None:
        _ask_handler(text)


def _report(_message: dict[str, Any]) -> None:
    from zoya import diagnostics

    diagnostics.send_report()


def _read_commands(child: subprocess.Popen) -> None:
    from zoya import shutdown, updates

    plain = {"stop": shutdown.stop, "quit": shutdown.quit_zoya, "update": updates.offer}
    with_message = {"forget": _forget, "report": _report, "ask": _ask}
    for line in child.stdout:
        try:
            message = json.loads(line)
            name = message.get("cmd")
        except (json.JSONDecodeError, AttributeError):
            continue
        if name in plain:
            target, args = plain[name], ()
        elif name in with_message:
            target, args = with_message[name], (message,)
        else:
            continue
        threading.Thread(target=target, args=args, name="zoya-overlay-command", daemon=True).start()


def send(message: dict[str, Any]) -> None:
    with contextlib.suppress(queue.Full):
        _queue.put_nowait(json.dumps(message))


def start(presence: bool = True) -> str:
    """Launch the overlay child. It always carries the menu-bar Stop / Quit and the quit key;
    with `presence` it also shows the stage overlay, subscribed to Zoya's events."""
    global _child, _presence
    if _alive():
        return "on"
    _presence = presence
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stderr = OVERLAY_LOG.open("a", encoding="utf-8")
    _child = subprocess.Popen(
        [sys.executable, "-m", "zoya.overlay", *([] if presence else [CONTROLS_ONLY_ARG])],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
    )
    threading.Thread(target=_write_loop, args=(_child,), name="zoya-overlay", daemon=True).start()
    threading.Thread(
        target=_read_commands, args=(_child,), name="zoya-overlay-commands", daemon=True
    ).start()
    if not presence:
        return f"controls only (pid {_child.pid})"
    for name in (events.NARRATE, events.EARCON, events.TASK, events.CONFIRMATION, events.OVERLAY):
        events.subscribe(name, _on_event)
    return f"on (pid {_child.pid}, log {OVERLAY_LOG})"


if __name__ == "__main__":
    from zoya.overlay_app import run

    sys.exit(run(controls_only=CONTROLS_ONLY_ARG in sys.argv))
