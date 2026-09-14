"""Spotify web recipes: play the exact song asked for (owner's failure: the last-played track
played).

Checked on the owner's signed-in Zoya profile, 2026-09-14: `open.spotify.com/search/<q>/tracks`
lists `[data-testid=tracklist-row]`; each row's play button has aria-label "Play <title> by
<artists>" and
only takes the pointer while the row is hovered. After the click, `[data-testid=now-playing-widget]`
says "Now playing: Love Me Not by Ravyn Lenae". Playback needs Widevine (browser.py launch
switches).

The play button goes through Guard 2 (`browser.click_checked`); the result is spoken only after the
now-playing bar shows that exact title, so Zoya never claims a song she didn't start.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import quote

from strands import tool

from zoya import safety
from zoya.tools import ToolError, browser
from zoya.tools.handoff import handoff_to_user

BASE = "https://open.spotify.com"
WAIT_MS = 8000
MAX_ROWS = 10
PLAY_PREFIX = "Play "
NOW_PLAYING_WAIT_S = 6.0
NOW_PLAYING_POLL_S = 0.3
HOVER_SETTLE_MS = 300
MS_PER_S = 1000
# The list moves 32 px down ~0.35 s after its rows appear (live, 2026-09-15). A hover before that
# leaves the pointer off the row, the button stays hidden, and the click waits 15 s on "<div>
# intercepts pointer events" (3 of 3 fresh launches). So hover until the button is on top twice.
ROW_BUTTON_ON_TOP_JS = """(row, prefix) => {
  const b = [...row.querySelectorAll('button')].find(e => (e.ariaLabel || '').startsWith(prefix));
  if (!b) return false;
  const r = b.getBoundingClientRect();
  return b.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)); }"""
SIGNED_IN = "[data-testid=user-widget-link]"
SIGNED_OUT = "[data-testid=login-button]"
BY = re.compile(r"^Play (?P<title>.+) by (?P<artists>.+)$")


def search_url(query: str) -> str:
    """URL template (tests/test_harness.py): the tracks tab of Spotify's search."""
    return f"{BASE}/search/{quote(query.strip(), safe='')}/tracks"


def pick_track(song: str, artist: str, labels: list[str]) -> int | None:
    """Index of the row to play from its "Play <title> by <artists>" labels. Parser, tested.

    Exact title first (ignoring case, punctuation and "(feat. …)"), then a title that starts with
    the song; the artist, when given, must be among the artists. None when nothing matches.
    """
    wanted, wanted_artist = safety.normalise(song), safety.normalise(artist)
    exact, prefix = None, None
    for index, label in enumerate(labels):
        match = BY.match(label.strip())
        if not match:
            continue
        title = safety.normalise(
            re.sub(r"\((?:feat|ft|with)\.?[^)]*\)", "", match["title"], flags=re.I)
        )
        if wanted_artist and wanted_artist not in safety.normalise(match["artists"]):
            continue
        if title == wanted and exact is None:
            exact = index
        elif title.startswith(wanted) and prefix is None:
            prefix = index
    return exact if exact is not None else prefix


def _play_labels(page: Any) -> list[str]:
    rows = page.locator("[data-testid=tracklist-row]")
    rows.first.wait_for(timeout=WAIT_MS)
    return [
        row.locator(f"button[aria-label^='{PLAY_PREFIX}']").first.get_attribute("aria-label") or ""
        for row in rows.all()[:MAX_ROWS]
    ]


@tool
def spotify_search(query: str) -> str:
    """Search songs on Spotify web and list the top tracks.

    Args:
        query: Song, artist or album.
    """
    browser.goto(search_url(query))
    labels = browser.on_page(_play_labels)
    listing = "\n".join(label.removeprefix(PLAY_PREFIX) for label in labels[:5] if label)
    return f"Spotify tracks for {query}:\n" + safety.wrap_untrusted(listing)


def needs_sign_in(page: Any) -> bool:
    """Positive signals after the app loads: the header shows the account widget when signed in
    and a "Log in" button when not (both checked live, 2026-09-15). Not sure (neither within
    WAIT_MS) → try the song; only a sign-in page or the "Log in" button asks the user."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    try:
        page.locator(f"{SIGNED_IN}, {SIGNED_OUT}").first.wait_for(timeout=WAIT_MS)
    except PlaywrightTimeout:
        return bool(browser.sign_in_wall(page))
    if page.locator(SIGNED_IN).count():
        return False
    return bool(page.locator(SIGNED_OUT).count() or browser.sign_in_wall(page))


def _now_playing(page: Any) -> str:
    widget = page.locator("[data-testid=now-playing-widget]")
    return (widget.first.get_attribute("aria-label") or "") if widget.count() else ""


@tool
def spotify_play_song(song: str, artist: str = "") -> str:
    """Play one exact song on Spotify web (searches, then presses play on that track).

    Args:
        song: The song title, e.g. "Love Me Not".
        artist: The artist, if the user said one.
    """
    if not song.strip():
        raise ToolError("Which song should I play?")
    browser.goto(search_url(f"{song} {artist}"))
    if browser.on_page(needs_sign_in):
        handoff_to_user("sign_in")
        return "Spotify needs you to sign in first."
    labels = browser.on_page(_play_labels)
    index = pick_track(song, artist, labels)
    if index is None:
        raise ToolError(f"I couldn't find {song} on Spotify.")
    title = BY.match(labels[index])["title"]

    def find(page: Any) -> Any:
        row = page.locator("[data-testid=tracklist-row]").nth(index)
        button = row.locator(f"button[aria-label^='{PLAY_PREFIX}']").first
        deadline = time.monotonic() + WAIT_MS / MS_PER_S
        was_on_top = False
        while time.monotonic() < deadline:
            page.mouse.move(0, 0)  # a fresh mouseenter each try
            row.hover()
            page.wait_for_timeout(HOVER_SETTLE_MS)
            on_top = row.evaluate(ROW_BUTTON_ON_TOP_JS, PLAY_PREFIX)
            if on_top and was_on_top:
                break
            was_on_top = on_top
        return button

    browser.click_checked(browser.probe_with(find), labels[index])
    deadline = time.monotonic() + NOW_PLAYING_WAIT_S
    while time.monotonic() < deadline:
        playing = browser.on_page(_now_playing)
        if safety.normalise(title) in safety.normalise(playing):
            return f"Playing {labels[index].removeprefix(PLAY_PREFIX)} on Spotify."
        time.sleep(NOW_PLAYING_POLL_S)
    raise ToolError(f"I pressed play on {title}, but Spotify isn't showing it as playing.")


TOOLS = [spotify_search, spotify_play_song]
