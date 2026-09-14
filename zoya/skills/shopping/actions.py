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
import threading
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote_plus, urlparse

from strands import tool

from zoya import cache, events, recipes, safety, speech, tasks
from zoya.tools import ToolError, browser
from zoya.tools.handoff import alert, handoff_to_user
from zoya.tools.memory import remember

HOST = "www.amazon.in"
BASE = f"https://{HOST}"
SEARCH_CACHE_TTL_S = 5 * 60  # prices move; a repeat within a conversation shouldn't reload
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
    "buy_now": "#buy-now-button",
    # Amazon Now (QCom) listings, e.g. eggs: no price on the row, no button on /dp, only "See All
    # Buying Choices", whose side panel holds the offer's Add to cart (owner's profile 2026-09-15).
    "see_offers": "#buybox-see-all-buying-choices",
    "offers_panel": "#aod-container",
    "offer_add_to_cart": (
        "#aod-container #freshAddToCartButton input, #aod-container input[name='submit.addToCart']"
    ),
    "product_title": "#productTitle",
    # Active cart only: "Saved for later" rows share the class (owner's run read 18 "items" with 10
    # saved-for-later ones among them, while checkout had 6).
    "cart_item": "#sc-active-cart div.sc-list-item[data-asin]",
    "cart_item_title": ".sc-product-title, .a-truncate-full",
    "cart_delete": "input[name^='submit.delete-active.']",
    "cart_subtotal": "#sc-subtotal-amount-activecart",
    # Groceries sit in the Amazon Now cart ("proceedToALMCheckout-<id>", page /tez/browse/cart);
    # the retail cart holds everything else. Checked on the owner's account 2026-09-14.
    "proceed_grocery": "input[name^='proceedToALMCheckout']",
    "proceed": "input[name='proceedToRetailCheckout']",
    "place_order": (
        "#submitOrderButtonId input, #placeYourOrder input, input[name='placeYourOrder1']"
    ),
}
ORDER_PLACED = re.compile(r"order placed|thank you, your order|order (?:is )?confirmed", re.I)
THANK_YOU_PATH = re.compile(r"thankyou|thank-you|order-confirmation", re.I)
PAYMENT_STEP_PATH = re.compile(r"^/checkout/p/[^/]+/(?:pay|offers)\b", re.I)
CHECKOUT_PATH = re.compile(r"^/(?:tez/browse/cart|gp/buy/|checkout/)", re.I)
PLACE_ORDER_NAME = re.compile(r"place (?:your )?order|^pay\b", re.I)
ADD_MONEY = re.compile(r"add money", re.I)
SUMMARY_START = re.compile(r"bill summary|order summary|review your items", re.I)
SUMMARY_END = re.compile(r"you might have missed|add more items|customers also bought", re.I)
SUMMARY_MAX_CHARS = 1500
SUMMARY_BILL = re.compile(r"bill summary|order summary|order total", re.I)
MAX_SPOKEN_ITEMS = 5
CONFIRMATION_PAGE_WAIT_MS = 3000
STORE_CLOSED = re.compile(r"store is closed[^\n]*", re.I)
ORDER_TOTAL = re.compile(
    r"(?:order total|grand total|to pay)\s*:?\s*(₹\s*\d[\d,]*(?:\.\d{1,2})?)", re.I
)
SPONSORED = "Sponsored"
MIN_ITEM_WORD_CHARS = 3
FILLER_WORDS = frozenset({"the", "and", "that", "this", "one", "item", "from", "with", "for", "my"})
ITEM_WORDS_FOR_CHECK = 4  # the first words of a title: what a checkout page shows untruncated
PANEL_SETTLE_MS = 1000
PAYMENT_ROW = "xpath=ancestor::*[self::label or contains(@class,'pmts')][1]"
PAYMENT_NAME_MAX_CHARS = 60


class FinalAnswer(ToolError):
    """The site's own answer (a closed store, nothing to remove). Tools return it as their result
    instead of failing, so neither a skill fallback nor the brain retries other listings for it."""


class NoBuyNow(FinalAnswer):
    """The product page has no Buy Now (Amazon Now groceries): add it to the cart instead."""


@dataclass(frozen=True)
class CheckoutState:
    host: str
    path: str
    text: str
    has_order_control: bool  # a "Place your order" / "Add Money to Place Order" / "Pay" button


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
                "sponsored": "yes" if row.get_by_text(SPONSORED, exact=True).count() else "",
            }
        )
    return results


def _result_lines(results: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{n}. {r['title']} — {r['price'] or 'price in the offers panel'}"
        + (f", {r['rating']}" if r["rating"] else "")
        + (", sponsored ad" if r.get("sponsored") else "")
        for n, r in enumerate(results, start=1)
    )


def _search(query: str) -> list[dict[str, str]]:
    """Results from the cache (read-only, SEARCH_CACHE_TTL_S) or the live page."""
    args = {"query": query}
    results = cache.get("amazon_search", args)
    if results is None:
        browser.goto(search_url(query))
        if browser.on_page(browser.sign_in_wall):
            handoff_to_user("captcha")
            raise FinalAnswer("Amazon wants a check before showing results.")
        results = browser.on_page(_read_results)
        cache.put("amazon_search", args, results, SEARCH_CACHE_TTL_S)
    _last_results[:] = results
    _last_query[0] = query
    events.emit(events.EarconEvent("progress-step"))
    return results


@tool
def amazon_search(query: str) -> str:
    """Search Amazon.in and read the top results with price and rating (from the live page).

    Args:
        query: What to buy, e.g. "Amul milk 1 litre".
    """
    try:
        results = _search(query)
    except FinalAnswer as answer:
        return str(answer)
    return f"Amazon.in results for {query}:\n" + safety.wrap_untrusted(_result_lines(results))


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
    chosen = _chosen(result_number)
    try:
        browser.click_checked(browser.probe_with(_add_to_cart_finder(chosen)), "Add to Cart")
    except FinalAnswer as answer:
        return str(answer)  # the brain says it as is instead of retrying other listings
    events.emit(events.EarconEvent("add-to-cart"))
    return f"Added to cart: {chosen['title']} ({chosen['price'] or 'price in the offers panel'})."


def _chosen(result_number: int) -> dict[str, str]:
    if not 1 <= result_number <= len(_last_results):
        raise ToolError("Search Amazon first, then tell me which result to add.")
    chosen = _last_results[result_number - 1]
    product_url(chosen["asin"])  # validates the ASIN before it goes into a selector
    return chosen


def _on_product_page(page: Any, asin: str) -> None:
    if f"/dp/{asin}" not in page.url:
        page.goto(product_url(asin), wait_until="domcontentloaded")
    if browser.sign_in_wall(page):
        raise FinalAnswer("Amazon needs you to sign in first.")


def _offer_button(page: Any, asin: str) -> Any:
    """Amazon Now listings: open "See All Buying Choices" (a side panel, nothing is bought) and
    take the offer's Add to cart. A closed store is said as Amazon words it."""
    _on_product_page(page, asin)
    see = page.locator(SELECTORS["see_offers"]).filter(visible=True)
    if not see.count():
        return None
    see.first.click()
    page.locator(SELECTORS["offers_panel"]).first.wait_for(timeout=WAIT_MS)
    page.wait_for_timeout(PANEL_SETTLE_MS)  # the offers render after the panel frame
    panel = page.locator(SELECTORS["offers_panel"]).first
    if closed := STORE_CLOSED.search(panel.inner_text()):
        notice = closed.group(0).strip().rstrip(".")
        raise FinalAnswer(f"Amazon Now sells this, and its {notice}. Nothing was added.")
    button = page.locator(SELECTORS["offer_add_to_cart"]).filter(visible=True)
    return button.first if button.count() else None


def _add_to_cart_finder(chosen: dict[str, str]) -> Any:
    asin = chosen["asin"]
    row_selector = f"{SELECTORS['result']}[data-asin='{asin}']"

    def find(page: Any) -> Any:
        """Cheapest first by the site recipe: the row's own button (groceries), the product
        page's button, or the Amazon Now offers panel."""
        strategies = {
            "row": lambda: _visible(
                page.locator(row_selector).locator(SELECTORS["result_add_to_cart"])
            ),
            "product_page": lambda: _product_button(page, asin, "add_to_cart"),
            "offers_panel": lambda: _offer_button(page, asin),
        }
        _, button = recipes.first_found(HOST, "add to cart", strategies)
        if button is None:
            raise ToolError("This product can't be added to the cart right now.")
        return button

    return find


def _visible(locator: Any) -> Any:
    visible = locator.filter(visible=True)
    return visible.first if visible.count() else None


def _product_button(page: Any, asin: str, name: str) -> Any:
    _on_product_page(page, asin)
    return _visible(page.locator(SELECTORS[name]))


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
        return "Your Amazon cart is empty (saved-for-later items don't count)."
    listing = "\n".join(f"{n}. {item}" for n, item in enumerate(items[:MAX_SPOKEN_ITEMS], 1))
    more = f"\n…and {len(items) - MAX_SPOKEN_ITEMS} more" if len(items) > MAX_SPOKEN_ITEMS else ""
    return safety.wrap_untrusted(
        f"Cart ({len(items)} items, not counting saved for later), subtotal {subtotal}:\n"
        f"{listing}{more}"
    )


def match_cart_item(titles: list[str], item: str) -> int:
    """Decision (tests/test_harness.py): the one cart line the user named, by its words.

    Every word of `item` (3+ letters) must be in the title. No line or several lines → ToolError:
    removing the wrong thing, or two things, is never a guess.
    """
    wanted = [
        w
        for w in safety.normalise(item).split()
        if len(w) >= MIN_ITEM_WORD_CHARS and w not in FILLER_WORDS
    ]
    if not wanted:
        raise ToolError("Tell me which item to remove, by its name.")
    hits = [
        n for n, title in enumerate(titles) if set(wanted) <= set(safety.normalise(title).split())
    ]
    if not hits:
        raise FinalAnswer(f"I don't see {item} in your Amazon cart.")
    if len(hits) > 1:
        names = "; ".join(titles[n][:60] for n in hits[:MAX_SPOKEN_ITEMS])
        raise FinalAnswer(f"Several cart items match {item}: {names}. Which one?")
    return hits[0]


@tool
def amazon_cart_remove(item: str) -> str:
    """Remove one item from the Amazon.in cart (the cart only; nothing is bought or cancelled).

    Args:
        item: Words from the item's name, e.g. "48 Laws of Power".
    """
    browser.goto(CART_URL)
    removed: list[str] = []

    def find(page: Any) -> Any:
        rows = page.locator(SELECTORS["cart_item"])
        rows.first.wait_for(timeout=WAIT_MS)
        titles = [_text(row.locator(SELECTORS["cart_item_title"])) for row in rows.all()]
        index = match_cart_item(titles, item)
        button = _visible(rows.nth(index).locator(SELECTORS["cart_delete"]))
        if button is None:
            raise ToolError("I can't find the Delete link for that item.")
        removed[:] = [titles[index]]
        return button

    try:
        browser.click_checked(browser.probe_with(find), "Delete")
    except FinalAnswer as answer:
        return str(answer)
    return safety.wrap_untrusted(f"Removed from the cart: {removed[0] if removed else item}.")


def checkout_summary(text: str) -> str:
    """Parser (tests/test_harness.py): the items and bill parts of a checkout page's text, without
    the address block and the recommendations after them. Falls back to the page's end."""
    flat = " ".join(text.split())
    parts = []
    for start in SUMMARY_START.finditer(flat):
        end = SUMMARY_END.search(flat, start.end())
        parts.append(flat[start.start() : end.start() if end else None][:SUMMARY_MAX_CHARS])
    return "\n".join(parts) if parts else flat[-SUMMARY_MAX_CHARS:]


def _checkout_state(page: Any) -> CheckoutState:
    page.wait_for_load_state("domcontentloaded")
    landed = re.compile(f"{SUMMARY_BILL.pattern}|{ORDER_PLACED.pattern}", re.I)
    with contextlib.suppress(Exception):  # judged below from whatever loaded
        page.get_by_text(landed).first.wait_for(timeout=WAIT_MS)
    controls = page.get_by_role("button", name=PLACE_ORDER_NAME).count()
    controls += page.locator(SELECTORS["place_order"]).count()
    url = urlparse(page.url)
    return CheckoutState(url.netloc, url.path, page.inner_text("body"), controls > 0)


def checkout_verdict(state: CheckoutState) -> str:
    """Parser (tests/test_harness.py): "ok", "order_placed" or "unexpected" after Proceed.

    An order confirmation / thank-you page means Amazon finalised without Zoya's confirmation.
    Amazon's newer checkout (/checkout/p/<id>/pay, then /offers with a Prime upsell) asks for a
    payment method before any Place-order control exists: "payment_step" (owner's profile
    2026-09-15). Anything else without a Place-order (or Add-money) control is unexpected.
    """
    if ORDER_PLACED.search(state.text) or THANK_YOU_PATH.search(state.path):
        return "order_placed"
    if CHECKOUT_PATH.search(state.path) and state.has_order_control:
        return "ok"
    if PAYMENT_STEP_PATH.search(state.path):
        return "payment_step"
    return "unexpected"


def _verify_no_order(state: CheckoutState) -> None:
    verdict = checkout_verdict(state)
    if verdict == "ok":
        return
    if verdict == "unexpected":
        raise ToolError("The checkout page didn't open the way I expected, so I stopped.")
    said = (
        "Warning: Amazon is showing an order confirmation that you did not confirm. Please check "
        "your Amazon orders now. I've alerted your trusted contact."
    )
    events.emit(events.EarconEvent("error"))
    speech.narrate(said)
    safety.audit_event(
        safety.Action("purchase", "Proceed to checkout", target=state.host),
        "unexpected order placed",
    )
    threading.Thread(target=alert, args=(state.host, "unexpected_order"), daemon=True).start()
    raise safety.ConfirmationDeclined(said)


def _read_checkout(page: Any) -> str:
    """The checkout is a client-rendered page: wait for its bill before reading."""
    page.get_by_text(SUMMARY_BILL).first.wait_for(timeout=WAIT_MS)
    return checkout_summary(page.inner_text("body"))


@tool
def amazon_checkout(groceries: bool = True) -> str:
    """Open Amazon.in checkout from the cart and read the order summary (items, bill, total).
    Nothing is ordered: that needs amazon_place_order and the user's spoken confirm.

    Args:
        groceries: True for the grocery (Amazon Now/Fresh) cart, False for the regular cart.
    """
    browser.goto(CART_URL)

    def find(page: Any) -> Any:
        form = page.locator(SELECTORS["proceed_grocery" if groceries else "proceed"])
        if not form.filter(visible=True).count():
            raise ToolError("That cart is empty, so there's nothing to check out.")
        return form.filter(visible=True).first

    # Guard 2 like any click: only the exact KNOWN_SAFE_CLICKS proceed forms pass without asking.
    browser.click_checked(browser.probe_with(find), "Proceed to checkout")
    return "Checkout page:\n" + safety.wrap_untrusted(_opened_checkout())


def _opened_checkout() -> str:
    """After Proceed or Buy Now: signed in, no order was placed, then the page's summary."""
    if browser.on_page(browser.sign_in_wall):
        handoff_to_user("sign_in")
        raise FinalAnswer("Amazon needs you to sign in before checkout.")
    state = browser.on_page(_checkout_state)
    if checkout_verdict(state) == "payment_step":
        method = browser.on_page(_selected_payment)
        raise FinalAnswer(
            "Amazon's checkout is asking you to choose a payment method"
            + (f" ({method} is selected)" if method else "")
            + " and may offer Prime. I stopped there, so nothing was ordered."
        )
    _verify_no_order(state)
    events.emit(events.EarconEvent("progress-step"))
    return browser.on_page(_read_checkout)


def _selected_payment(page: Any) -> str:
    """The payment method Amazon pre-selected, as its row reads ("Visa ending in 1060")."""
    checked = page.locator("input[type=radio]:checked").locator(PAYMENT_ROW)
    return safety.UNTRUSTED_TAG.sub("", _text(checked))[:PAYMENT_NAME_MAX_CHARS]


def order_total(summary: str) -> str:
    """Parser (tests/test_harness.py): the payable total a checkout summary shows ("₹399.00"), the
    last "Order total" / "To pay" / "Grand total" amount. "" when there is none."""
    found = ORDER_TOTAL.findall(" ".join(summary.split()))
    return found[-1].replace(" ", "") if found else ""


@tool
def amazon_buy_now(result_number: int) -> str:
    """Buy one product from the last amazon_search on its own with the product page's Buy Now:
    opens checkout for that item (live check 2026-09-15: Amazon.in also adds it to the cart).
    Nothing is ordered: that needs amazon_place_order and the user's spoken confirm.

    Args:
        result_number: Its number in the last search results (1 = first).
    """
    chosen = _chosen(result_number)
    try:
        # KNOWN_SAFE_CLICKS lists this exact form; _opened_checkout proves no order came back.
        browser.click_checked(browser.probe_with(_buy_now_finder(chosen)), "Buy Now")
        summary = _opened_checkout()
    except FinalAnswer as answer:
        return str(answer)
    return "Checkout page (only this item):\n" + safety.wrap_untrusted(summary)


def _buy_now_finder(chosen: dict[str, str]) -> Any:
    def find(page: Any) -> Any:
        button = _product_button(page, chosen["asin"], "buy_now")
        if button is None:
            raise NoBuyNow("This one has no Buy Now on Amazon; I can add it to the cart instead.")
        return button

    return find


def pick_result(results: list[dict[str, str]]) -> int:
    """Decision (tests/test_harness.py): the result number to buy for a spoken "buy X": the first
    listing that isn't a sponsored ad, else the first. The spoken confirm names it before paying."""
    if not results:
        raise FinalAnswer("Amazon found nothing for that.")
    return next((n for n, r in enumerate(results, 1) if not r.get("sponsored")), 1)


def _check_item(title: str) -> str:
    """The first words of a title: what the screen check looks for on the checkout page."""
    return " ".join(title.split()[:ITEM_WORDS_FOR_CHECK])


@tool
def amazon_buy(query: str) -> str:
    """One call for "buy X on Amazon": search, pick the first non-sponsored listing, Buy Now (only
    that item; Amazon.in also adds it to the cart), read the checkout, then place the order
    through Zoya's spoken confirmation. Amazon Now items (groceries) are added to the cart instead.

    Args:
        query: What to buy, e.g. "48 Laws of Power book".
    """
    try:
        chosen = _last_results[pick_result(_search(query)) - 1]
        found = f"Found {_check_item(chosen['title'])}" + (
            f", {chosen['price']}." if chosen["price"] else "."
        )
        tasks.say(found)
        browser.click_checked(browser.probe_with(_buy_now_finder(chosen)), "Buy Now")
        summary = _opened_checkout()
    except NoBuyNow:
        try:
            browser.click_checked(browser.probe_with(_add_to_cart_finder(chosen)), "Add to Cart")
        except FinalAnswer as closed:
            return str(closed)
        events.emit(events.EarconEvent("add-to-cart"))
        return (
            f"Added {_check_item(chosen['title'])} to your Amazon cart. Say check out when ready."
        )
    except FinalAnswer as answer:
        return str(answer)
    total = order_total(summary)
    if not total:
        raise ToolError("I couldn't read the order total on the checkout page.")
    return amazon_place_order(total, _check_item(chosen["title"]))


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
        page.get_by_text(SUMMARY_BILL).first.wait_for(timeout=WAIT_MS)
        button = page.locator(SELECTORS["place_order"]).filter(visible=True)
        if not button.count():
            button = page.get_by_role("button", name=PLACE_ORDER_NAME).filter(visible=True)
        if not button.count():
            raise ToolError("I can't find the Place your order button. Open checkout first.")
        if ADD_MONEY.search(button.first.inner_text() or ""):
            raise ToolError(
                "Amazon wants money added before this order, so I stopped. Please set up a "
                "payment method on Amazon first. Nothing was ordered."
            )
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


TOOLS = [
    amazon_search,
    amazon_add_to_cart,
    amazon_buy_now,
    amazon_buy,
    amazon_cart,
    amazon_cart_remove,
    amazon_checkout,
    amazon_place_order,
]
