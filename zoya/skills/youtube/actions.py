"""YouTube recipes (Layer 1: 0 model calls when a trigger matches).

Selectors checked on the owner's signed-in Zoya profile, 2026-09-14: search results
`ytd-channel-renderer a#main-link` (href "/@MrBeast"), `ytd-video-renderer a#video-title`; watch
page `ytd-watch-metadata h1`, subscribe button aria-label "Subscribe to MrBeast.", like button
aria-label "like this video along with … other people" + aria-pressed, comment box
`#simplebox-placeholder`.

Opening and playing are navigations (GET) — never a risky action by URL. Subscribe, like and comment
publish as the user: `browser.confirm_then_click` always asks with a summary read from the live
page.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

from strands import tool

from zoya import cache, safety
from zoya.tools import ToolError, browser
from zoya.tools.memory import secret_reason

BASE = "https://www.youtube.com"
WAIT_MS = 8000
CHANNEL_URL_TTL_S = 7 * 24 * 3600
MAX_RESULTS = 5
CHANNEL_PATH = re.compile(r"^/(?:@[\w.-]+|channel/[\w-]+|c/[\w-]+)/?$")
WATCH_PATH = "/watch"
SUBSCRIBE_PREFIX = "subscribe to "
LIKE_PREFIX = "like this video"


def search_url(query: str) -> str:
    """URL template (tests/test_harness.py)."""
    return f"{BASE}/results?search_query={quote_plus(query.strip())}"


def _results(page: Any, selector: str) -> list[tuple[str, str]]:
    """(name, absolute href) of the visible results matching `selector`."""
    page.locator(selector).first.wait_for(timeout=WAIT_MS)
    rows = []
    for link in page.locator(selector).all()[:MAX_RESULTS]:
        href = link.get_attribute("href") or ""
        rows.append((" ".join(link.inner_text().split()), urljoin(BASE, href)))
    return rows


def best_match(query: str, rows: list[tuple[str, str]]) -> tuple[str, str]:
    """The row whose name equals the query (normalised), else the first. Parser, tested."""
    wanted = safety.normalise(query).replace(" ", "")
    for name, href in rows:
        if safety.normalise(name).replace(" ", "").startswith(wanted):
            return name, href
    return rows[0]


@tool
def youtube_search(query: str) -> str:
    """Search YouTube and list the top videos and channels.

    Args:
        query: What to search for.
    """
    browser.goto(search_url(query))
    rows = browser.on_page(
        lambda page: _results(
            page, "ytd-channel-renderer a#main-link, ytd-video-renderer a#video-title"
        )
    )
    listing = "\n".join(f"{i}. {name}" for i, (name, _) in enumerate(rows, start=1))
    return f"YouTube results for {query}:\n" + safety.wrap_untrusted(listing)


@tool
def youtube_open_channel(name: str) -> str:
    """Open a YouTube channel's page: searches, then opens the matching channel (never guesses
    @handles).

    Args:
        name: The channel name, e.g. "MrBeast".
    """
    if not name.strip():
        raise ToolError("Which channel should I open?")
    args = {"name": name}
    found = cache.get("youtube_open_channel", args)
    if found is None:
        browser.goto(search_url(name))
        rows = browser.on_page(lambda page: _results(page, "ytd-channel-renderer a#main-link"))
        if not rows:
            raise ToolError(f"I couldn't find a channel called {name} on YouTube.")
        found = best_match(name, rows)
    title, url = found
    if not CHANNEL_PATH.match(urlparse(url).path):
        raise ToolError(f"I couldn't find a channel called {name} on YouTube.")
    browser.goto(url)
    cache.put("youtube_open_channel", args, found, CHANNEL_URL_TTL_S)
    return f"Opened {title.split(' @')[0]}'s channel on YouTube."


@tool
def youtube_play_video(title: str) -> str:
    """Play a YouTube video: searches for it and opens the top matching video, which starts playing.

    Args:
        title: The video title or a description, e.g. "MrBeast Escape 100 Cops".
    """
    if not title.strip():
        raise ToolError("Which video should I play?")
    browser.goto(search_url(title))
    rows = browser.on_page(lambda page: _results(page, "ytd-video-renderer a#video-title"))
    if not rows:
        raise ToolError(f"I couldn't find a video called {title}.")
    name, url = best_match(title, rows)
    if urlparse(url).path != WATCH_PATH:
        raise ToolError(f"I couldn't find a video called {title}.")
    browser.goto(url)
    if not browser.on_page(_video_playing):
        return f"I opened {name} on YouTube, but it isn't playing yet."
    return f"Playing {name} on YouTube."


PLAYING_JS = (
    "() => { const v = document.querySelector('video');"
    " return v && !v.paused && v.currentTime > 0 }"
)


def _video_playing(page: Any) -> bool:
    """The watch page's <video> advanced (autoplay switch in browser.py; an ad counts)."""
    try:
        page.wait_for_function(PLAYING_JS, timeout=WAIT_MS)
    except Exception:  # noqa: BLE001 — Playwright TimeoutError: say it isn't playing yet
        return False
    return True


def _on_watch_or_channel(page: Any) -> None:
    path = urlparse(page.url).path
    if urlparse(page.url).netloc != "www.youtube.com" or not (
        path == WATCH_PATH or CHANNEL_PATH.match(path)
    ):
        raise ToolError("Open the video or channel first.")


def _names(target: browser.Target) -> list[str]:
    return [safety.normalise(label) for label in target.facts.labels if label.strip()]


@tool
def youtube_subscribe() -> str:
    """Subscribe to the channel of the YouTube video or channel page that is open. Zoya asks the
    user to confirm out loud first."""

    def find(page: Any) -> Any:
        _on_watch_or_channel(page)
        return (
            page.get_by_role("button", name=re.compile(r"^Subscribe to ", re.I))
            .filter(visible=True)
            .first
        )

    target = browser.on_page(lambda page: browser._probe_locator(page, find(page)))
    channel = next(
        (
            n.removeprefix(SUBSCRIBE_PREFIX)
            for n in _names(target)
            if n.startswith(SUBSCRIBE_PREFIX)
        ),
        "",
    )
    if not channel:
        raise ToolError("I can't find the subscribe button. You may already be subscribed.")

    def still(again: browser.Target) -> bool:
        return f"{SUBSCRIBE_PREFIX}{channel}" in _names(again)

    browser.confirm_then_click(
        browser.probe_with(find), safety.Action("post", "subscribe to", target=channel), still
    )
    return f"Subscribed to {channel}. The user confirmed it out loud."


@tool
def youtube_like() -> str:
    """Like the YouTube video that is open. Zoya asks the user to confirm out loud first."""

    def find(page: Any) -> Any:
        if urlparse(page.url).path != WATCH_PATH:
            raise ToolError("Open the video first.")
        return page.locator("ytd-watch-metadata button[aria-label^='like this video' i]").first

    def facts(page: Any) -> tuple[str, str]:
        button = find(page)
        title = page.locator("ytd-watch-metadata h1").first.inner_text().strip()
        return button.get_attribute("aria-pressed") or "", title

    pressed, title = browser.on_page(facts)
    if pressed == "true":
        return "You've already liked this video."

    def still(again: browser.Target) -> bool:
        return any(name.startswith(LIKE_PREFIX) for name in _names(again))

    browser.confirm_then_click(
        browser.probe_with(find), safety.Action("post", "like the video", target=title), still
    )
    return f"Liked {title}. The user confirmed it out loud."


@tool
def youtube_comment(text: str) -> str:
    """Post a comment on the YouTube video that is open. Zoya reads the comment back and asks the
    user to confirm out loud before posting.

    Args:
        text: The comment, e.g. "great video".
    """
    comment = " ".join(text.split())
    if not comment:
        raise ToolError("What should the comment say?")
    if secret_reason(comment):
        raise ToolError("That comment looks like it has a code or card number, so I won't post it.")

    def open_editor(page: Any) -> str:
        if urlparse(page.url).path != WATCH_PATH:
            raise ToolError("Open the video first.")
        page.locator("ytd-comments").first.scroll_into_view_if_needed()
        # Opens the empty comment box by its fixed id: nothing is posted by this click.
        page.locator("#simplebox-placeholder").first.click()
        editor = page.locator("#contenteditable-root").first
        browser.fill_checked(editor, comment, "comment")
        return page.locator("ytd-watch-metadata h1").first.inner_text().strip()

    title = browser.on_page(open_editor)

    def find(page: Any) -> Any:
        return page.locator("ytd-commentbox #submit-button button").first

    def still(again: browser.Target) -> bool:
        typed = browser.on_page(
            lambda page: page.locator("#contenteditable-root").first.inner_text()
        )
        return "comment" in _names(again) and " ".join(typed.split()) == comment

    browser.confirm_then_click(
        browser.probe_with(find),
        safety.Action("post", "post the comment", target=f'"{comment}" on {title}'),
        still,
    )
    return f"Posted the comment on {title}. The user confirmed it out loud."


TOOLS = [
    youtube_search,
    youtube_open_channel,
    youtube_play_video,
    youtube_subscribe,
    youtube_like,
    youtube_comment,
]
