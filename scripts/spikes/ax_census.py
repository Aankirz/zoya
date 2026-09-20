"""Spike 1 — accessibility tree census. Run: .venv/bin/python scripts/spikes/ax_census.py"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import AppKit
import ApplicationServices as AS

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya.screen import _ax
from zoya.tools.ax import LISTED_ROLES, NAME_ATTRIBUTES, PRESSABLE_ROLES

APPS = [
    "Mail",
    "Notes",
    "Safari",
    "Google Chrome",
    "Messages",
    "System Settings",
    "Finder",
    "Calendar",
    "Preview",
    "Reminders",
    "Music",
    "Terminal",
    "Visual Studio Code",
    "Slack",
    "zoom.us",
    "WhatsApp",
    "Spotify",
    "Photos",
    "Maps",
    "App Store",
]


SEED = {
    "Preview": ["open", "-a", "Preview", "/System/Library/CoreServices/DefaultDesktop.heic"],
    "Safari": ["open", "-a", "Safari", "https://en.wikipedia.org/wiki/Accessibility"],
    "Google Chrome": ["open", "-a", "Google Chrome", "https://en.wikipedia.org/wiki/Accessibility"],
}
WALK_CAP = 6000
WALK_DEADLINE_S = 20.0
MESSAGING_TIMEOUT_S = 2.0
WINDOW_TIMEOUT_S = 12.0
LAUNCH_TIMEOUT_S = 25.0
ACTIVATE_SETTLE_S = 3.0
MANUAL_AX_SETTLE_S = 3.0


def installed(app: str) -> str | None:
    out = subprocess.run(
        ["mdfind", f'kMDItemKind == "Application" && kMDItemFSName == "{app}.app"'],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out.splitlines()[0] if out else None


def _running(app: str, path: str) -> object | None:
    candidates = [
        r
        for r in AppKit.NSWorkspace.sharedWorkspace().runningApplications()
        if r.activationPolicy() == AppKit.NSApplicationActivationPolicyRegular
    ]
    for r in candidates:
        url = r.bundleURL()
        if url is not None and str(url.path()).rstrip("/") == path.rstrip("/"):
            return r
    for r in candidates:
        if str(r.localizedName()) == app:
            return r
    return None


def activate(app: str, path: str) -> object | None:
    subprocess.run(SEED.get(app, ["open", "-a", app]), capture_output=True)
    deadline = time.monotonic() + LAUNCH_TIMEOUT_S
    running = None
    while time.monotonic() < deadline:
        running = _running(app, path)
        if running is not None and running.isFinishedLaunching():
            break
        time.sleep(0.5)
    if running is None:
        return None
    running.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    time.sleep(ACTIVATE_SETTLE_S)
    element = AS.AXUIElementCreateApplication(running.processIdentifier())
    AS.AXUIElementSetMessagingTimeout(element, MESSAGING_TIMEOUT_S)

    window_deadline = time.monotonic() + WINDOW_TIMEOUT_S
    while not (_ax(element, "AXWindows") or []) and time.monotonic() < window_deadline:
        time.sleep(0.5)
    return element


def walk(app_element: object) -> dict:
    windows = list(_ax(app_element, "AXWindows") or [])
    queue = [(w, 1) for w in windows]
    total = actionable = named = listed = titled = described = 0
    depth = 0
    started = time.monotonic()
    truncated = False
    while queue:
        if total >= WALK_CAP or time.monotonic() - started > WALK_DEADLINE_S:
            truncated = True
            break
        element, level = queue.pop(0)
        total += 1
        depth = max(depth, level)
        role = str(_ax(element, "AXRole") or "")
        title = _ax(element, "AXTitle")
        description = _ax(element, "AXDescription")
        titled += bool(isinstance(title, str) and title.strip())
        described += bool(isinstance(description, str) and description.strip())
        has_name = any(isinstance(v := _ax(element, a), str) and v.strip() for a in NAME_ATTRIBUTES)
        named += has_name
        if role in PRESSABLE_ROLES:
            actionable += 1
        if role in LISTED_ROLES and has_name:
            listed += 1
        queue += [(c, level + 1) for c in (_ax(element, "AXChildren") or [])]
    return {
        "windows": len(windows),
        "total_elements": total,
        "actionable": actionable,
        "named_any": named,
        "ax_title": titled,
        "ax_description": described,
        "listed_named": listed,
        "depth": depth,
        "truncated": truncated,
        "seconds": round(time.monotonic() - started, 3),
    }


def census(app: str) -> dict:
    path = installed(app)
    if not path:
        return {"app": app, "installed": False}
    element = activate(app, path)
    if element is None:
        return {"app": app, "installed": True, "path": path, "error": "did not come to front"}
    plain = walk(element)

    AS.AXUIElementSetAttributeValue(element, "AXManualAccessibility", True)
    AS.AXUIElementSetAttributeValue(element, "AXEnhancedUserInterface", True)
    time.sleep(MANUAL_AX_SETTLE_S)
    manual = walk(element)
    return {
        "app": app,
        "installed": True,
        "path": path,
        "default": plain,
        "with_manual_accessibility": manual,
        "manual_ax_helps": manual["total_elements"] > plain["total_elements"] * 1.2,
    }


def main() -> None:
    results = [census(a) for a in APPS]
    out = Path(__file__).resolve().parents[2] / "logs/spikes/ax_census.json"
    out.write_text(json.dumps(results, indent=2))
    print(
        "| App | Elements | Actionable | Named | AXTitle | AXDesc | Depth | Read (s) "
        "| Manual AX helps |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        if not r.get("installed"):
            print(f"| {r['app']} | _not installed_ | | | | | | | |")
            continue
        if "error" in r:
            print(f"| {r['app']} | _{r['error']}_ | | | | | | | |")
            continue
        d = max((r["default"], r["with_manual_accessibility"]), key=lambda x: x["total_elements"])
        print(
            f"| {r['app']} | {d['total_elements']}{'+' if d['truncated'] else ''} | "
            f"{d['actionable']} | {d['named_any']} | {d['ax_title']} | {d['ax_description']} | "
            f"{d['depth']} | {d['seconds']} | {'yes' if r['manual_ax_helps'] else 'no'} |"
        )
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
