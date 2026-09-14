"""T0 direct-command tools (§9.4): open apps/URLs, media keys, volume, time.

No model calls, no shell strings: every process gets an argv list.
`open -a` needs no macOS permission (AUDIT §3).
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from urllib.parse import urlparse

from strands import tool

from zoya.config import APP_LOOKUP_TIMEOUT_S, OSASCRIPT_TIMEOUT_S
from zoya.tools import ToolError

VOLUME_STEP = 15
MAX_VOLUME = 100
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
def open_app(app_name: str, prefer_web: bool = True) -> str:
    """Open an application by name, e.g. "Spotify" or "Notes".

    Services with a website (Spotify, YouTube, WhatsApp, Gmail) open in the browser unless the
    user asked for the app: easier for a blind user and where Phase 4 automates the page.

    Args:
        app_name: The app or service name.
        prefer_web: False only when the user explicitly said "app".
    """
    name = app_name.strip()
    if not name:
        raise ToolError("Which app should I open?")
    if prefer_web and (site := WEB_APPS.get(name.lower())):
        open_url(site)
        return f"{name} is open in your browser."
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


# Owner (2026-09-14): open these in the browser, not the Mac app (D58).
WEB_APPS = {
    "spotify": "open.spotify.com",
    "youtube": "youtube.com",
    "youtube music": "music.youtube.com",
    "whatsapp": "web.whatsapp.com",
    "gmail": "mail.google.com",
}

# No free-form AppleScript tool (coordinator review, §12.2): text-based allow-lists are
# bypassable (e.g. the ¬ line continuation), and the brain passes untrusted text. Every
# script Zoya runs is a fixed string below; the model only picks keys.
MEDIA_APPS = {"music": "Music", "spotify": "Spotify"}
MEDIA_COMMANDS = {
    "play": "play",
    "pause": "pause",
    "playpause": "playpause",
    "next": "next track",
    "previous": "previous track",
}


@tool
def media_control(action: str, app: str = "spotify") -> str:
    """Control music playback. action: play | pause | playpause | next | previous.
    app: spotify | music."""
    app_name = MEDIA_APPS.get(app.strip().lower())
    command = MEDIA_COMMANDS.get(action.strip().lower())
    if app_name is None or command is None:
        raise ToolError("I can only play, pause or skip songs in Spotify or Music.")
    osascript(f'tell application "{app_name}" to {command}')
    return "Done."


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


TOOLS = [open_app, open_url, media_control, set_volume, volume_up, volume_down, mute, get_time]
