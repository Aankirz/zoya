"""Browser tools, the minimum Phase 3 needs (§9.7, D11): open, read, click, type. Phase 4 extends.

Every click goes through Guard 2 (zoya/safety.py). The label check reads the element Playwright
will really click, never the text the model asked for. A pay/send/delete/submit label needs the
user's voice confirmation, and purchases also need an OCR check of the total. Typing refuses
password/OTP/card fields (§12.1). Page text reaches the model only inside <untrusted_content>.

Playwright's sync API must stay on the thread that started it, so one worker thread owns the
browser and every call is bounded.

APIs (Playwright 1.62, https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context,
https://playwright.dev/python/docs/actionability — click waits until the element itself receives
the pointer event, so an overlay can't take the click; https://playwright.dev/python/docs/locators).
"""

from __future__ import annotations

import concurrent.futures
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from strands import tool

from zoya import safety, screen
from zoya.config import BROWSER_ACTION_TIMEOUT_S, BROWSER_PROFILE_DIR, BROWSER_TEXT_MAX_CHARS
from zoya.tools import ToolError
from zoya.tools.fast import normalise_url

MS_PER_S = 1000
PLAYWRIGHT_TIMEOUT_MS = int(BROWSER_ACTION_TIMEOUT_S * MS_PER_S)
WORKER_SLACK_S = 5.0  # a Playwright call times out on its own first
LABEL_ATTRIBUTES = ("aria-label", "title", "value", "alt", "placeholder")
# The nearest clickable ancestor-or-self: clicking a <span> inside "Place order" presses the button.
CLICKABLE = "xpath=ancestor-or-self::*[self::button or self::a or @role='button' or self::input][1]"
CHROME_APP = "Chrome"

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="zoya-browser")
_state: dict[str, Any] = {}


def _on_browser[T](call: Callable[[], T]) -> T:
    try:
        return _executor.submit(call).result(timeout=BROWSER_ACTION_TIMEOUT_S + WORKER_SLACK_S)
    except concurrent.futures.TimeoutError as error:
        raise ToolError("The browser took too long to respond.") from error
    except ToolError:
        raise
    except Exception as error:  # noqa: BLE001 — Playwright errors become a polite spoken reason
        raise ToolError(f"The browser couldn't do that ({type(error).__name__}).") from error


def _page() -> Any:
    """The dedicated Zoya Chrome profile (D11), launched once, on the browser thread."""
    page = _state.get("page")
    if page is not None and not page.is_closed():
        return page
    from playwright.sync_api import sync_playwright

    if "playwright" not in _state:
        _state["playwright"] = sync_playwright().start()
    context = _state["playwright"].chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE_DIR), channel="chrome", headless=False
    )
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT_MS)
    _state["page"] = context.pages[0] if context.pages else context.new_page()
    return _state["page"]


@tool
def browser_open(url: str) -> str:
    """Open a web page in Zoya's browser so it can be read and clicked, e.g. "amazon.in".

    Args:
        url: http(s) address.
    """
    address = normalise_url(url)
    title = _on_browser(lambda: (_page().goto(address), _page().bring_to_front(), _page().title()))
    return f"Opened {title[-1] or address}."


@tool
def browser_read() -> str:
    """Read the text of the page open in Zoya's browser (title, then visible text)."""

    def read() -> str:
        page = _page()
        return f"{page.title()}\n{page.inner_text('body')}"

    return safety.wrap_untrusted(_on_browser(read)[:BROWSER_TEXT_MAX_CHARS])


# --- Guard 2 -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Target:
    handle: Any  # the exact element that will be clicked
    labels: list[str]
    title: str
    host: str  # shown in Chrome's address bar: proves the screenshot is this page, not a stale one


def _locate(page: Any, text: str) -> Any:
    for locator in (
        page.get_by_role("button", name=text),
        page.get_by_role("link", name=text),
        page.get_by_label(text),
        page.get_by_text(text),
    ):
        visible = locator.filter(visible=True)
        if visible.count():
            return visible.first
    raise ToolError(f"I can't find {text} on the page.")


def _labels(locator: Any) -> list[str]:
    """Text, attributes and accessible name of the element and its clickable ancestor.

    Playwright's own getters, not page JavaScript that a page could override.
    """
    labels: list[str] = []
    for part in (locator, locator.locator(CLICKABLE)):
        if not part.count():
            continue
        labels.append(part.inner_text())
        labels.append(part.aria_snapshot())  # computed accessible name, incl. aria-labelledby
        labels += [value for a in LABEL_ATTRIBUTES if (value := part.get_attribute(a))]
    return labels


def _probe(text: str) -> Target:
    page = _page()
    locator = _locate(page, text)
    return Target(
        locator.element_handle(), _labels(locator), page.title(), urlparse(page.url).netloc
    )


def _screen_rows(target: Target) -> list[str]:
    started = time.monotonic()
    _on_browser(lambda: _page().bring_to_front())
    jpeg = screen.capture_window_jpeg(CHROME_APP, target.title)
    captured = time.monotonic()
    rows = safety.rows_from_ocr(screen.detect_text(jpeg))
    if not any(target.host and target.host in row.replace(" ", "") for row in rows):
        raise ToolError("I couldn't confirm the screenshot shows this page. Let's try again.")
    safety.log_safety_timing(
        event="screen_check",
        capture_ms=round((captured - started) * MS_PER_S),
        ocr_ms=round((time.monotonic() - captured) * MS_PER_S),
    )
    return rows


def _verified_action(
    risky: safety.RiskyLabel, target: Target, amount: str, item: str
) -> safety.Action:
    """The summary from screen evidence: the agent's amount and item must be visible on screen."""
    if not item.strip():
        raise ToolError(
            "Before clicking that, read the page and call browser_click again with `item` set to "
            "the item, recipient or file exactly as shown."
        )
    rows = _screen_rows(target)
    if not safety.target_on_screen(item, rows):
        raise ToolError(f"I can't see {item} on the screen. Read the page again.")
    if risky.kind != "purchase":
        return safety.Action(risky.kind, risky.say, target=item.strip())
    claimed = safety.parse_claimed_amount(amount)
    if claimed is None:
        raise ToolError(
            "Before paying, read the order total and call browser_click again with `amount` set "
            "to it, e.g. ₹2,847."
        )
    if not safety.amount_on_screen(claimed[0], rows):
        raise ToolError(
            f"The total on the screen doesn't match {amount}. Read the order total again."
        )
    return safety.Action(
        "purchase", risky.say, target=item.strip(), amount=safety.spoken_amount(*claimed)
    )


def _click(handle: Any) -> None:
    _on_browser(lambda: handle.click(timeout=PLAYWRIGHT_TIMEOUT_MS))


@tool
def browser_click(text: str, amount: str = "", item: str = "") -> str:
    """Click a button or link on the page by its visible text.

    Paying, ordering, sending, deleting or submitting makes Zoya ask the user out loud first;
    for those pass what the page shows.

    Args:
        text: The button or link text, e.g. "Add to cart".
        amount: For purchases: the order total exactly as shown, e.g. "₹2,847".
        item: For purchases, messages or deletions: the item, recipient or file as shown.
    """
    target = _on_browser(lambda: _probe(text))
    risky = safety.risky_label(target.labels)
    if risky is None:
        _click(target.handle)
        return f"Clicked {text}."
    action = _verified_action(risky, target, amount, item)

    def live() -> safety.Action:
        """Re-probe right before acting: same element, same risky label, same screen evidence."""
        again = _on_browser(lambda: _probe(text))
        same = _on_browser(lambda: again.handle.evaluate("(a, b) => a === b", target.handle))
        now = safety.risky_label(again.labels)
        if not same or now is None or now.say != risky.say:
            return safety.Action("changed", "changed")
        return _verified_action(now, again, amount, item)

    safety.require_confirmation(action, current=live)
    _click(target.handle)
    return f"Clicked {risky.say}. The user confirmed it out loud."


@tool
def browser_type(field: str, text: str) -> str:
    """Type text into a field on the page, found by its label or placeholder.

    Never used for passwords, OTPs or card numbers: the user types those themselves.

    Args:
        field: The field's label or placeholder, e.g. "Search".
        text: What to type.
    """

    def fill() -> None:
        locator = _locate(_page(), field)
        attrs = {a: locator.get_attribute(a) or "" for a in ("type", "autocomplete", "name", "id")}
        name = f"{field} {attrs['name']} {attrs['id']}"
        if safety.is_secret_field(attrs["type"], attrs["autocomplete"], name):
            raise ToolError("That's a password or code field. Please type it yourself; I'll wait.")
        locator.fill(text)

    _on_browser(fill)
    return f"Typed into {field}."


TOOLS = [browser_open, browser_read, browser_click, browser_type]
