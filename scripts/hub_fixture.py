"""Run the built app's Hub and pill on made-up data, never the owner's history (P3c review).

    uv run python scripts/hub_fixture.py                  # light; Ctrl-C to quit
    uv run python scripts/hub_fixture.py --dark
    uv run python scripts/hub_fixture.py --shots design/p3c/final/site

It starts dist/Zoya.app's overlay child (the Hub and the pill, real glass) with HOME pointed at a
fresh fixture folder, so no voice, no Chrome and no real logs are involved. With --shots it walks
every page through Accessibility and captures the Hub window, then the pill states.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import ApplicationServices as AX
import Foundation
import Quartz

REPO = Path(__file__).resolve().parent.parent
BINARY = REPO / "dist" / "Zoya.app" / "Contents" / "MacOS" / "Zoya"
OPEN_HUB_NOTICE = "app.zoya.Zoya.openHub"
PAGES = ("today", "history", "memory", "setup", "voice")
SHOT_PAGES = (*PAGES, "plan")
SETTLE_S = 1.6
START_S = 4.0

REQUESTS = (
    (0, "21:41", "play kesariya on spotify", "spotify_play_song", True, None),
    (0, "20:12", "open notes", "open_app", True, None),
    (0, "19:30", "search amazon for wireless mice", "amazon_search", True, None),
    (0, "18:02", "buy the boat earphones", "amazon_place_order", True, "stop"),
    (0, "16:18", "remember i like masala chai", "memory_add", True, None),
    (1, "10:05", "open safari", "open_app", True, None),
    (1, "09:40", "order the usb-c cable", "amazon_place_order", True, "confirmed"),
    (1, "09:12", "play lo-fi on youtube", "youtube_play_video", False, None),
    (2, "22:30", "set a reminder to call mom at six", "set_reminder", True, None),
)
SAID = {
    "play kesariya on spotify": "Playing Kesariya by Arijit Singh.",
    "search amazon for wireless mice": "Five mice. The cheapest is ₹549.",
    "play lo-fi on youtube": "YouTube didn't load, so I stopped.",
}
MEMORIES = (
    "You like masala chai, not coffee.",
    "Your sister's name is Priya.",
    "You prefer window seats on flights.",
    "Your gym is Cult on 12th Main.",
)


def _stamp(days_ago: int, clock: str) -> str:
    hour, minute = (int(part) for part in clock.split(":"))
    day = datetime.now().astimezone() - timedelta(days=days_ago)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()


def _lines(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), "utf-8")


def _logs(home: Path) -> None:
    timing, confirms, said = [], [], []
    for index, (days, clock, command, tool, ok, decision) in enumerate(REQUESTS):
        task, at = f"fixture{index}", _stamp(days, clock)
        timing.append({"at": at, "task_id": task, "route": "skill", "ok": ok, "command": command})
        timing[-1]["tool"] = tool
        if decision:
            confirms.append(
                {
                    "task_id": task,
                    "at": at,
                    "action": "place order",
                    "amount": "₹1,249" if decision == "stop" else "₹399",
                    "recipient_or_item": "amazon.in",
                    "decision": decision,
                }
            )
        if command in SAID:
            said.append({"at": at, "task_id": task, "said": SAID[command]})
    logs = home / "Library" / "Logs" / "Zoya"
    _lines(logs / "timing.log", timing)
    _lines(logs / "confirmations.log", confirms)
    _lines(logs / "said.log", said)


def make_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="zoya-fixture-"))
    _logs(home)
    zoya = home / ".zoya"
    zoya.mkdir()
    memories = [
        {"id": secrets.token_hex(16), "at": _stamp(3, "12:00"), "content": text}
        for text in MEMORIES
    ]
    (zoya / "memory.json").write_text(json.dumps(memories), "utf-8")
    grants = {"microphone": False, "accessibility": True, "screen": True, "automation": True}
    (zoya / "permissions.json").write_text(json.dumps(grants), "utf-8")
    (zoya / "setup.json").write_text(json.dumps({"finished": _stamp(4, "09:00")}), "utf-8")
    settings = {"pillPosition": "bottom", "hotkey": "fn-shift"}
    (zoya / "settings.json").write_text(json.dumps(settings), "utf-8")
    return home


def launch(home: Path, dark: bool) -> subprocess.Popen:
    if not BINARY.exists():
        sys.exit("Build first: ./build")
    style = ["-AppleInterfaceStyle", "Dark"] if dark else ["-NSRequiresAquaSystemAppearance", "YES"]
    child = subprocess.Popen(
        [str(BINARY), "-m", "zoya.overlay", *style],
        stdin=subprocess.PIPE,
        text=True,
        env={**os.environ, "HOME": str(home)},
    )
    time.sleep(START_S)
    Foundation.NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_(
        OPEN_HUB_NOTICE, None
    )
    time.sleep(SETTLE_S)
    return child


def send(child: subprocess.Popen, message: dict) -> None:
    child.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    child.stdin.flush()


def _windows(pid: int) -> list[dict]:
    listed = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, 0)
    return [w for w in listed if w["kCGWindowOwnerPID"] == pid]


def hub_window(pid: int) -> int:
    def area(window: dict) -> float:
        bounds = window["kCGWindowBounds"]
        return bounds["Width"] * bounds["Height"]

    return max(_windows(pid), key=area)["kCGWindowNumber"]


def _attribute(element: object, name: str) -> object:
    error, value = AX.AXUIElementCopyAttributeValue(element, name, None)
    return value if error == 0 else None


def _find(element: object, role: str) -> object:
    if _attribute(element, "AXRole") == role:
        return element
    for child in _attribute(element, "AXChildren") or []:
        if found := _find(child, role):
            return found
    return None


def _plan_button(element: object) -> object:
    names = (_attribute(element, "AXTitle"), _attribute(element, "AXDescription"))
    if _attribute(element, "AXRole") == "AXButton" and any(
        str(name or "").startswith("Plan") for name in names
    ):
        return element
    for child in _attribute(element, "AXChildren") or []:
        if found := _plan_button(child):
            return found
    return None


def _cell_name(row: object) -> str:
    cells = _attribute(row, "AXChildren") or []
    return str(_attribute(cells[0], "AXDescription") or "") if cells else ""


def select_page(pid: int, page: str) -> None:
    windows = _attribute(AX.AXUIElementCreateApplication(pid), "AXWindows") or []
    app = max(windows, key=lambda w: len(_attribute(w, "AXChildren") or []))
    if page == "plan":
        AX.AXUIElementPerformAction(_plan_button(app), "AXPress")
        time.sleep(SETTLE_S)
        return
    table = _find(app, "AXTable")
    if table is None:
        sys.exit("No sidebar table: give this terminal Accessibility access.")
    rows = [r for r in _attribute(table, "AXRows") or [] if _cell_name(r)]
    AX.AXUIElementSetAttributeValue(rows[PAGES.index(page)], "AXSelected", True)
    time.sleep(SETTLE_S)


def capture(window: int, path: Path) -> None:
    """A window capture: nothing behind it is recorded, but glass shows untinted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["screencapture", "-x", "-o", f"-l{window}", str(path)], check=True)


def capture_region(pid: int, window: int, path: Path) -> None:
    """The window as it is on screen, glass included; an opaque window hides what is behind."""
    bounds = next(w for w in _windows(pid) if w["kCGWindowNumber"] == window)["kCGWindowBounds"]
    rect = ",".join(str(int(bounds[k])) for k in ("X", "Y", "Width", "Height"))
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["screencapture", "-x", f"-R{rect}", str(path)], check=True)


PILL_STATES = (
    ("idle", {"k": "state", "state": "idle"}, None),
    ("listening", {"k": "state", "state": "listening"}, None),
    (
        "listening-chips",
        {"k": "state", "state": "listening"},
        {"k": "intent", "text": "play kesariya on spotify", "chips": ["spotify", "kesariya"]},
    ),
    ("thinking", {"k": "state", "state": "thinking", "step": "Searching Spotify"}, None),
    ("speaking", {"k": "zoya", "text": "Playing Kesariya by Arijit Singh."}, None),
    ("confirm", {"k": "state", "state": "waiting", "stake": "Place the order, ₹1,249"}, None),
    ("error", {"k": "state", "state": "error", "step": "Can't reach Spotify"}, None),
)


def pill_window(pid: int, hub: int) -> int:
    return next(w["kCGWindowNumber"] for w in _windows(pid) if w["kCGWindowNumber"] != hub)


def shots(child: subprocess.Popen, folder: Path, theme: str) -> None:
    window = hub_window(child.pid)
    for page in SHOT_PAGES:
        select_page(child.pid, page)
        capture_region(child.pid, window, folder / f"{page}-{theme}.png")
    for name, state, extra in PILL_STATES:
        send(child, state)
        if extra:
            send(child, extra)
        time.sleep(SETTLE_S)
        capture(pill_window(child.pid, window), folder / "pill" / f"{name}-{theme}.png")


FINDER_BOUNDS = (240, 160, 1040, 660)
GLOW_ROOM = 16


def _finder(home: Path, script: str) -> None:
    subprocess.run(["osascript", "-e", f'tell application "Finder" to {script}'], check=False)


def _finder_rect(home: Path) -> tuple[int, int, int, int]:
    subprocess.run(["open", str(home)], check=True)
    time.sleep(SETTLE_S)
    left, top, right, bottom = FINDER_BOUNDS
    _finder(home, f"set bounds of front window to {{{left}, {top}, {right}, {bottom}}}")
    time.sleep(SETTLE_S / 2)
    return left, top, right - left, bottom - top


def _grab(rect: tuple[int, int, int, int], path: Path) -> None:
    x, y, width, height = rect
    area = f"{x - GLOW_ROOM},{y - GLOW_ROOM},{width + 2 * GLOW_ROOM},{height + 2 * GLOW_ROOM}"
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["screencapture", "-x", f"-R{area}", str(path)], check=True)


def glow_shots(child: subprocess.Popen, home: Path, folder: Path, theme: str) -> None:
    """Zoya acting in a Finder window on the fixture folder: glow, cursor, ripple, wait, stop."""
    rect = _finder_rect(home)
    x, y, width, height = rect
    send(child, {"k": "state", "state": "acting", "step": "Pressing a button", "tool": "ax_press"})
    time.sleep(SETTLE_S)
    _grab(rect, folder / f"glow-acting-{theme}.png")
    send(child, {"k": "ring", "rect": [x + width * 0.7, y + height * 0.6, 120, 28]})
    time.sleep(0.3)
    _grab(rect, folder / f"glow-cursor-ripple-{theme}.png")
    time.sleep(SETTLE_S)
    send(child, {"k": "state", "state": "waiting", "stake": "Place the order, ₹1,249"})
    time.sleep(SETTLE_S)
    _grab(rect, folder / f"glow-waiting-{theme}.png")
    send(child, {"k": "state", "state": "stopped"})
    time.sleep(0.4)
    _grab(rect, folder / f"glow-stopped-{theme}.png")
    _finder(home, "close front window")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--shots", type=Path)
    parser.add_argument("--glow", type=Path, help="capture the glow and cursor into this folder")
    args = parser.parse_args()
    if subprocess.run(["pgrep", "-x", "Zoya"], capture_output=True).returncode == 0:
        sys.exit("Zoya is running: quit it first, or its Hub opens too.")
    home = make_home()
    print(f"fixture home: {home}", flush=True)
    child = launch(home, args.dark)
    send(child, {"k": "state", "state": "idle"})
    try:
        if args.glow:
            glow_shots(child, home, args.glow, "dark" if args.dark else "light")
            return 0
        if args.shots:
            shots(child, args.shots, "dark" if args.dark else "light")
            return 0
        child.wait()
    except KeyboardInterrupt:
        pass
    finally:
        child.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
