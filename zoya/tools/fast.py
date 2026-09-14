"""T0 direct-command tools (§9.4): open apps/URLs, allow-listed AppleScript, volume, time.

No model calls, no shell strings: every process gets an argv list.
`open -a` needs no macOS permission (AUDIT §3).
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from urllib.parse import urlparse

from strands import tool

from zoya.config import APP_LOOKUP_TIMEOUT_S, APPLESCRIPT_ALLOWED_APPS, OSASCRIPT_TIMEOUT_S
from zoya.tools import ToolError

VOLUME_STEP = 15
MAX_VOLUME = 100
APP_REFERENCE = re.compile(r"\b(?:application|app)\b", re.I)
APP_NAMED = re.compile(r'\b(?:application|app)\s+"([^"]+)"', re.I)
FORBIDDEN_APPLESCRIPT = re.compile(
    r"\bdo\s+shell\s+script\b|\b(?:run|load|store)\s+script\b|\bopen\s+location\b"
    r"|\b(?:read|write)\b|\bdisplay\s+(?:dialog|alert)\b|\bchoose\b|«",
    re.I,
)
UNSAFE_LOOKUP_CHARS = re.compile(r"['\"\\*]")


def _run(argv: list[str], timeout: float = OSASCRIPT_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def osascript(script: str, *args: str) -> str:
    """Run AppleScript; user text goes in as argv (`on run argv`), never spliced into code."""
    try:
        result = _run(["osascript", "-e", script, *args])
    except subprocess.TimeoutExpired as error:
        raise ToolError(
            "The Mac took too long to answer. If it asked for permission, please allow it."
        ) from error
    if result.returncode != 0:
        raise ToolError("Sorry, the Mac didn't accept that command.")
    return result.stdout.strip()


def _find_app(name: str) -> str | None:
    """Spotlight lookup for an installed app containing `name` ("Chrome" → "Google Chrome")."""
    safe = UNSAFE_LOOKUP_CHARS.sub("", name).strip()
    if not safe:
        return None
    query = (
        "kMDItemContentType == 'com.apple.application-bundle'"
        f" && kMDItemDisplayName == '*{safe}*'cd"
    )
    result = _run(["mdfind", query], timeout=APP_LOOKUP_TIMEOUT_S)
    paths = [line for line in result.stdout.splitlines() if line.endswith(".app")]
    # ponytail: shortest path wins ("Spotify.app" beats "Spotify Helper.app");
    # rank by last-used date if it picks the wrong app.
    return min(paths, key=len) if paths else None


@tool
def open_app(app_name: str) -> str:
    """Open an application on this Mac by name, e.g. "Spotify" or "Notes"."""
    name = app_name.strip()
    if not name:
        raise ToolError("Which app should I open?")
    if _run(["open", "-a", name]).returncode == 0:
        return f"{name} is open."
    path = _find_app(name)
    if path and _run(["open", path]).returncode == 0:
        return f"{name} is open."
    raise ToolError(f"I can't find {name} on this Mac.")


def normalise_url(url: str) -> str:
    """Add https:// to bare domains; allow only http(s) so no file:// or custom schemes run."""
    candidate = url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or "." not in parsed.netloc:
        raise ToolError("That doesn't look like a web address I can open.")
    return candidate


@tool
def open_url(url: str) -> str:
    """Open a website in the default browser, e.g. "youtube.com"."""
    address = normalise_url(url)
    if _run(["open", address]).returncode != 0:
        raise ToolError("Sorry, I couldn't open that website.")
    return f"Opening {urlparse(address).netloc}."


def check_applescript_allowed(script: str) -> None:
    """Refuse scripts that run code outside the allow-listed apps.

    Every `app`/`application` reference must be a literal quoted name on the
    allow-list, so `application id "…"`, `app someVariable` and
    `app "Terminal"` are all refused. Model output is untrusted (§12.2).
    """
    if FORBIDDEN_APPLESCRIPT.search(script):
        raise ToolError("I'm not allowed to run that kind of script.")
    references = APP_REFERENCE.findall(script)
    named = [name.lower() for name in APP_NAMED.findall(script)]
    if not named or len(named) != len(references):
        raise ToolError("I'm not allowed to control that app with AppleScript.")
    if not set(named) <= APPLESCRIPT_ALLOWED_APPS:
        raise ToolError("I'm not allowed to control that app with AppleScript.")


@tool
def run_applescript(script: str) -> str:
    """Run AppleScript that controls only Notes, Music or Spotify (e.g. play/pause music).
    Use only when no dedicated tool fits."""
    check_applescript_allowed(script)
    output = osascript(script)
    return output or "Done."


@tool
def set_volume(level: int) -> str:
    """Set the Mac's output volume from 0 (silent) to 100 (loudest)."""
    clamped = max(0, min(MAX_VOLUME, int(level)))
    osascript(
        "on run argv\nset volume output volume (item 1 of argv as integer)\nend run", str(clamped)
    )
    return f"Volume set to {clamped} percent."


def change_volume(delta: int) -> str:
    current = int(osascript("output volume of (get volume settings)") or 0)
    return set_volume(current + delta)


@tool
def volume_up() -> str:
    """Turn the Mac's volume up a step."""
    return change_volume(VOLUME_STEP)


@tool
def volume_down() -> str:
    """Turn the Mac's volume down a step."""
    return change_volume(-VOLUME_STEP)


@tool
def mute() -> str:
    """Mute the Mac's sound output."""
    osascript("set volume with output muted")
    return "Muted."


@tool
def get_time() -> str:
    """Tell the current local time and date."""
    now = datetime.now()
    return f"It's {now:%-I:%M %p} on {now:%A, %-d %B}."


TOOLS = [open_app, open_url, run_applescript, set_volume, volume_up, volume_down, mute, get_time]
