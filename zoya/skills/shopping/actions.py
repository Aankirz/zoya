"""Amazon.in shopping recipes (Flow 6, §9.12): search, add to cart, read the cart, open checkout,
place the order through the spoken confirmation.

Grounding rule (§9.12): prices, items and the total come only from the live page.
`amazon_place_order`
goes through `browser.click_checked`: "Place your order" is a purchase label, so the agent's total
must equal every order-total row that Rekognition reads on a fresh screenshot, the item must be
visible, and the user must say "confirm" to a summary built from that evidence. With
`--order-limit` set (Done-when #5 test run), a payable total above it is never offered.

"Add to Cart" on www.amazon.in is the one click allowed without a question
(`safety.KNOWN_SAFE_CLICKS`): it is reversible and a cancel leaves the cart intact (Done-when #4).
Selectors: see `SELECTORS`, checked on the owner's signed-in profile (hand-off report).
"""

from __future__ import annotations

import contextlib
import re
from datetime import date
from typing import Any
from urllib.parse import quote_plus

from strands import tool

from zoya import events, safety
from zoya.tools import ToolError, browser
from zoya.tools.handoff import handoff_to_user
from zoya.tools.memory import remember

BASE = "https://www.amazon.in"
CART_URL = f"{BASE}/gp/cart/view.html"
WAIT_MS = 8000
MAX_RESULTS = 5
SELECTORS = {
    "result": "div[data-component-type='s-search-result'][data-asin]:not([data-asin=''])",
    "result_title": "h2",  # brand and name are separate <h2>s: "Amul" + "Taaza … 1 L Carton"
    "result_add_to_cart": "input[name='submit.addToCart']",  # grocery rows; their /dp page has none
    "price": ".a-price .a-offscreen",
    "rating": ".a-icon-alt",
    "add_to_cart": "#add-to-cart-button",
    "product_title": "#productTitle",
    "cart_item": "div.sc-list-item[data-asin]",
    "cart_item_title": ".sc-product-title, .a-truncate-full",
    "cart_subtotal": "#sc-subtotal-amount-activecart",
    "proceed": "input[name='proceedToRetailCheckout']",
    "place_order": (
        "#submitOrderButtonId input, #placeYourOrder input, input[name='placeYourOrder1']"
    ),
}
ORDER_PLACED = re.compile(r"order placed|thank you, your order", re.I)
MAX_SPOKEN_ITEMS = 5
CONFIRMATION_PAGE_WAIT_MS = 3000

_last_results: list[dict[str, str]] = []  # the most recent search, so "add the second one" works
_last_query: list[str] = [""]


def search_url(query: str) -> str:
    """URL template (tests/test_harness.py)."""
    return f"{BASE}/s?k={quote_plus(query.strip())}"


def _text(locator: Any) -> str:
    return " ".join(locator.first.inner_text().split()) if locator.count() else ""


def _read_results(page: Any) -> list[dict[str, str]]:
    page.locator(SELECTORS["result"]).first.wait_for(timeout=WAIT_MS)
    results = []
    for row in page.locator(SELECTORS["result"]).all()[:MAX_RESULTS]:
        price = row.locator(SELECTORS["price"])
        rating = row.locator(SELECTORS["rating"])
        results.append(
            {
                "asin": row.get_attribute("data-asin") or "",
                "title": " ".join(
                    " ".join(h.inner_text().split()) for h in row.locator("h2").all()
                ),
                "price": (price.first.text_content() or "").strip() if price.count() else "",
                "rating": (rating.first.text_content() or "").strip() if rating.count() else "",
            }
        )
    return results


@tool
def amazon_search(query: str) -> str:
    """Search Amazon.in and read the top results with price and rating (from the live page).

    Args:
        query: What to buy, e.g. "Amul milk 1 litre".
    """
    browser.goto(search_url(query))
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("captcha")
        return "Amazon wants a check before showing results."
    results = browser.on_page(_read_results)
    _last_results[:] = results
    _last_query[0] = query
    events.emit(events.EarconEvent("progress-step"))
    lines = [
        f"{n}. {r['title']} — {r['price'] or 'no price shown'}"
        + (f", {r['rating']}" if r["rating"] else "")
        for n, r in enumerate(results, start=1)
    ]
    return f"Amazon.in results for {query}:\n" + safety.wrap_untrusted("\n".join(lines))


def product_url(asin: str) -> str:
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise ToolError("That isn't an Amazon product I found.")
    return f"{BASE}/dp/{asin}"


@tool
def amazon_add_to_cart(result_number: int) -> str:
    """Add one product from the last amazon_search to the cart.

    Args:
        result_number: Its number in the last search results (1 = first).
    """
    if not 1 <= result_number <= len(_last_results):
        raise ToolError("Search Amazon first, then tell me which result to add.")
    chosen = _last_results[result_number - 1]
    product_url(chosen["asin"])  # validates the ASIN before it goes into a selector
    row_selector = f"{SELECTORS['result']}[data-asin='{chosen['asin']}']"
    if not browser.on_page(lambda page: page.locator(row_selector).count()):
        browser.goto(search_url(_last_query[0]))

    def find(page: Any) -> Any:
        """The row's own "Add to cart" (groceries), else the product page's button."""
        row_button = page.locator(row_selector).locator(SELECTORS["result_add_to_cart"])
        if row_button.filter(visible=True).count():
            return row_button.filter(visible=True).first
        page.goto(product_url(chosen["asin"]), wait_until="domcontentloaded")
        if browser.sign_in_wall(page):
            raise ToolError("Amazon needs you to sign in first.")
        button = page.locator(SELECTORS["add_to_cart"]).filter(visible=True)
        if not button.count():
            raise ToolError("This product can't be added to the cart right now.")
        return button.first

    browser.click_checked(browser.probe_with(find), "Add to Cart")
    events.emit(events.EarconEvent("add-to-cart"))
    return f"Added to cart: {chosen['title']} ({chosen['price']})."


def _read_cart(page: Any) -> tuple[list[str], str]:
    page.locator(f"{SELECTORS['cart_item']}, {SELECTORS['cart_subtotal']}").first.wait_for(
        timeout=WAIT_MS
    )
    items = [
        _text(row.locator(SELECTORS["cart_item_title"]))
        for row in page.locator(SELECTORS["cart_item"]).all()
    ]
    return [i for i in items if i], _text(page.locator(SELECTORS["cart_subtotal"]))


@tool
def amazon_cart() -> str:
    """Read the Amazon.in cart: items and subtotal, from the live page."""
    browser.goto(CART_URL)
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("sign_in")
        return "Amazon needs you to sign in first."
    items, subtotal = browser.on_page(_read_cart)
    if not items:
        return "Your Amazon cart is empty."
    listing = "\n".join(f"- {item}" for item in items[:MAX_SPOKEN_ITEMS])
    return safety.wrap_untrusted(f"Cart ({len(items)} items), subtotal {subtotal}:\n{listing}")


@tool
def amazon_checkout() -> str:
    """Open Amazon.in checkout from the cart and read the order summary (items, delivery, order
    total). Nothing is ordered: that needs amazon_place_order and the user's spoken confirm."""
    browser.goto(CART_URL)

    def proceed(page: Any) -> str:
        form = page.locator(SELECTORS["proceed"]).filter(visible=True)
        if not form.count():
            raise ToolError("The cart is empty, so there's nothing to check out.")
        # "Proceed to Buy" only opens the checkout page (GET-like navigation, nothing is bought),
        # so the recipe follows it by its fixed name, not by model text.
        form.first.click()
        page.wait_for_load_state("domcontentloaded")
        return page.url

    browser.on_page(proceed)
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("sign_in")
        return "Amazon needs you to sign in before checkout."
    events.emit(events.EarconEvent("progress-step"))
    return browser.browser_read()


def _order_confirmed(page: Any) -> bool:
    page.wait_for_timeout(CONFIRMATION_PAGE_WAIT_MS)
    return bool(ORDER_PLACED.search(page.inner_text("body")))


@tool
def amazon_place_order(order_total: str, items: str) -> str:
    """Place the order on the open Amazon.in checkout page. Zoya reads the real total from the
    screen and asks the user to confirm out loud; nothing is ordered otherwise.

    Args:
        order_total: The order total exactly as the checkout page shows it, e.g. "₹412.00".
        items: The item names as shown on the checkout page, e.g. "Amul Taaza Milk".
    """

    def find(page: Any) -> Any:
        button = page.locator(SELECTORS["place_order"]).filter(visible=True)
        if not button.count():
            button = page.get_by_role("button", name=re.compile("place your order", re.I))
        if not button.count():
            raise ToolError("I can't find the Place your order button. Open checkout first.")
        return button.first

    said, _ = browser.click_checked(
        browser.probe_with(find), "Place your order", order_total, items, require="purchase"
    )
    placed = browser.on_page(_order_confirmed)
    events.emit(events.EarconEvent("purchase"))
    amount = safety.parse_claimed_amount(order_total)
    spoken = safety.spoken_amount(*amount) if amount else order_total
    with contextlib.suppress(ToolError):  # a title with a long number can look like a card
        remember(
            f"Ordered {items} from Amazon.in on {date.today():%d %B %Y} for {spoken}",
            "order_history",
        )
    if not placed:
        return f"I pressed {said} after the user confirmed. Amazon hasn't confirmed the order yet."
    return f"Order placed for {spoken}. The user confirmed it out loud."


TOOLS = [amazon_search, amazon_add_to_cart, amazon_cart, amazon_checkout, amazon_place_order]
