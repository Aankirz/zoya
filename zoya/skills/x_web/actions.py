"""X (Twitter) recipe: post a tweet from the owner's signed-in Zoya profile (D11).

Posting publishes as the user: `browser.confirm_then_click` always asks with the exact text and its
character count, re-reads the compose box right before the click, and "Posted." is said only after
X shows its "Your post was sent" toast.

Selectors (x.com, stable data-testid attributes; each wait logs which one matched): compose box
`[data-testid=tweetTextarea_0]` (contenteditable), Post button `[data-testid=tweetButton]`, signed
in `[data-testid=SideNav_AccountSwitcher_Button]`, signed out `[data-testid=loginButton]` or the
/i/flow/login page, sent toast `[data-testid=toast]`.

Character count: X's weighted count (twitter-text v3 config, https://github.com/twitter/twitter-text/
blob/master/config/v3.json): code points in its ranges weigh 1, everything else (CJK, emoji) 2,
every URL 23; 280 is the standard limit.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from strands import tool

from zoya import safety
from zoya.tools import ToolError, browser
from zoya.tools.handoff import handoff_to_user
from zoya.tools.memory import secret_reason

log = logging.getLogger(__name__)

COMPOSE_URL = "https://x.com/compose/post"
WAIT_MS = 10000
SENT_WAIT_MS = 10000
MAX_WEIGHT = 280
URL_WEIGHT = 23
LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
URL = re.compile(r"https?://\S+|\b[\w-]+\.(?:com|org|net|io|ai|in|co|dev|app)(?:/\S*)?", re.I)
COMPOSE_BOX = "[data-testid=tweetTextarea_0]"
POST_BUTTON = "[data-testid=tweetButton]"
SIGNED_IN = "[data-testid=SideNav_AccountSwitcher_Button]"
SIGNED_OUT = "[data-testid=loginButton]"
LOGIN_PATH = "/i/flow/login"
TOAST = "[data-testid=toast]"
SENT_WORDS = "sent"


def tweet_length(text: str) -> int:
    """X's weighted character count. Parser, tested.

    ponytail: an emoji ZWJ sequence counts per code point (X counts it as 2); dictated tweets rarely
    have one, and X's own button stays disabled if we undercount.
    """
    total, rest = 0, text
    for url in URL.findall(text):
        total += URL_WEIGHT
        rest = rest.replace(url, "", 1)
    for ch in rest:
        light = any(low <= ord(ch) <= high for low, high in LIGHT_RANGES)
        total += 1 if light else 2
    return total


def check_tweet(text: str) -> tuple[str, int]:
    """(clean text, weighted length), or a ToolError the user hears. Never truncates. Tested."""
    clean = " ".join(text.split())
    if not clean:
        raise ToolError("What should the tweet say?")
    if secret_reason(clean):
        raise ToolError("That tweet looks like it has a code or card number, so I won't post it.")
    length = tweet_length(clean)
    if length > MAX_WEIGHT:
        raise ToolError(
            f"That tweet is {length} characters and X allows {MAX_WEIGHT}. "
            "Want me to shorten it?"
        )
    return clean, length


def needs_sign_in(page: Any) -> bool:
    """Positive signals: the account switcher when signed in, the login button or login page when
    not. Neither within WAIT_MS → only a VISIBLE sign-in wall asks (browser.sign_in_wall)."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    if urlparse(page.url).path.startswith(LOGIN_PATH):
        log.info("x sign-in: login page")
        return True
    try:
        page.locator(f"{SIGNED_IN}, {SIGNED_OUT}, {COMPOSE_BOX}").first.wait_for(timeout=WAIT_MS)
    except PlaywrightTimeout:
        return bool(browser.sign_in_wall(page))
    if page.locator(SIGNED_IN).count() or page.locator(COMPOSE_BOX).count():
        log.info("x sign-in: signed in")
        return False
    log.info("x sign-in: login button=%s", page.locator(SIGNED_OUT).count())
    return bool(page.locator(SIGNED_OUT).count() or browser.sign_in_wall(page))


def _box_text(page: Any) -> str:
    return " ".join(page.locator(COMPOSE_BOX).first.inner_text().split())


def _type_tweet(page: Any, text: str) -> None:
    """Into the compose box only (X's own editor, never a password field): real input events."""
    box = page.locator(COMPOSE_BOX).first
    box.wait_for(timeout=WAIT_MS)
    box.click()
    page.keyboard.press("Meta+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(text)
    if _box_text(page) != text:
        raise ToolError("X didn't take the text as I typed it, so I stopped. Nothing was posted.")


def _sent(page: Any) -> bool:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    toast = page.locator(TOAST).filter(has_text=re.compile(SENT_WORDS, re.I)).first
    try:
        toast.wait_for(timeout=SENT_WAIT_MS)
    except PlaywrightTimeout:
        return False
    log.info("x post: toast %r", " ".join(toast.inner_text().split())[:60])
    return True


@tool
def x_post(text: str) -> str:
    """Post a tweet on X from the user's account. Zoya reads back the exact text and character
    count and posts only after the user says "confirm" out loud.

    Args:
        text: The tweet, exactly as the user said it.
    """
    clean, length = check_tweet(text)
    browser.goto(COMPOSE_URL)
    if browser.on_page(needs_sign_in):
        handoff_to_user("sign_in")
        return "X needs you to sign in first."
    browser.on_page(lambda page: _type_tweet(page, clean))

    def find(page: Any) -> Any:
        return page.locator(POST_BUTTON).filter(visible=True).first

    def still(again: browser.Target) -> bool:
        ready = browser.on_page(
            lambda page: find(page).get_attribute("aria-disabled") != "true"
            and _box_text(page) == clean
        )
        return ready and any(name == "post" for name in map(safety.normalise, again.facts.labels))

    browser.confirm_then_click(
        browser.probe_with(find),
        safety.Action("post", "tweet", target=f'"{clean}", {length} characters'),
        still,
    )
    if not browser.on_page(_sent):
        raise ToolError("I pressed Post, but X didn't show it as sent. Check your profile.")
    return "Posted. X showed it as sent; the user confirmed it out loud."


TOOLS = [x_post]
