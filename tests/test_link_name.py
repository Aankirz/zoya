"""D143: a link's name is the aria snapshot's first line only; a link to a cart, checkout, payment
or order path still asks."""

import pytest

from zoya import safety
from zoya.tools import browser

SOUTH_GOA = (
    '- link "South Goa 1,171 properties":\n'
    "  - /url: https://stay.example/searchresults.html?checkin=2026-10-17&checkout=2026-10-19\n"
    '  - heading "South Goa" [level=3]'
)


def link(name: str, url_path: str = "/searchresults.html"):
    return safety.ClickFacts(labels=[name], is_link=True, host="stay.example", link_path=url_path)


def test_the_name_stops_at_the_first_line():
    assert safety.accessible_name(SOUTH_GOA) == "South Goa 1,171 properties"


def test_a_link_whose_query_mentions_checkout_no_longer_asks():
    assert safety.click_risk(link(safety.accessible_name(SOUTH_GOA))) is None


@pytest.mark.parametrize(
    "path", ["/checkout", "/cart", "/gp/cart/view.html", "/payment/step2", "/orders/123", "/order"]
)
def test_a_link_to_a_cart_checkout_payment_or_order_path_still_asks(path):
    assert safety.click_risk(link("Continue", path)) is not None


@pytest.mark.parametrize("name", ["Check out", "Proceed to checkout", "Place order", "Pay now"])
def test_a_link_named_for_money_still_asks(name):
    assert safety.click_risk(link(name)) is not None


PAGES = {
    "a path link": (
        '<a id="t" href="https://shop.example/gp/cart/view.html?x=1">Cart</a>',
        "/gp/cart/view.html",
    ),
    "a query-only mention": (
        '<a id="t" href="https://stay.example/search?checkout=2026-10-19">Goa</a>',
        "/search",
    ),
    "not a link": ('<button id="t">Go</button>', ""),
}


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as playwright:
        try:
            chrome = playwright.chromium.launch(channel="chrome", headless=True)
        except Error as error:
            pytest.skip(f"Chrome not available: {error}")
        yield chrome.new_page()
        chrome.close()


@pytest.mark.parametrize(("body", "path"), PAGES.values(), ids=PAGES.keys())
def test_the_page_fact_is_the_links_own_path(page, body, path):
    page.set_content(body)
    assert page.locator("#t").evaluate(browser.ELEMENT_SHAPE_JS)["linkPath"] == path
