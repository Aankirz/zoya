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
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("sign_in")
        return "Spotify needs you to sign in first."
    labels = browser.on_page(_play_labels)
    index = pick_track(song, artist, labels)
    if index is None:
        raise ToolError(f"I couldn't find {song} on Spotify.")
    title = BY.match(labels[index])["title"]

    def find(page: Any) -> Any:
        row = page.locator("[data-testid=tracklist-row]").nth(index)
        row.hover()
        page.wait_for_timeout(HOVER_SETTLE_MS)
        return row.locator(f"button[aria-label^='{PLAY_PREFIX}']").first

    browser.click_checked(browser.probe_with(find), labels[index])
    deadline = time.monotonic() + NOW_PLAYING_WAIT_S
    while time.monotonic() < deadline:
        playing = browser.on_page(_now_playing)
        if safety.normalise(title) in safety.normalise(playing):
            return f"Playing {labels[index].removeprefix(PLAY_PREFIX)} on Spotify."
        time.sleep(NOW_PLAYING_POLL_S)
    raise ToolError(f"I pressed play on {title}, but Spotify isn't showing it as playing.")


TOOLS = [spotify_search, spotify_play_song]
