"""Phase H money path: an order Zoya did not confirm is caught on any site, not just Amazon."""

import pytest

from zoya import safety
from zoya.tools import browser

CHECKOUT = "shop.example/checkout"
THANKS = "https://shop.example/pages/thank-you"
AT_CHECKOUT = browser.Target(None, safety.ClickFacts([], path="/checkout"), "", "shop.example")


@pytest.mark.parametrize(
    "text",
    [
        "Thank you for your order! Order #1042",
        "Your order has been placed.",
        "Your booking is confirmed",
        "Payment successful",
    ],
)
def test_a_confirmation_page_after_a_click_is_an_order(text):
    assert browser.order_happened(CHECKOUT, THANKS, text)


@pytest.mark.parametrize(
    ("was", "now", "text"),
    [
        (CHECKOUT, "https://shop.example/checkout", "Thank you for your order"),
        (CHECKOUT, "https://shop.example/account/orders", "Order placed 12 Sep. Your Orders"),
        (CHECKOUT, THANKS, "Continue shopping"),
    ],
)
def test_staying_put_or_an_orders_list_is_not_an_order(was, now, text):
    assert not browser.order_happened(was, now, text)


def test_an_unconfirmed_order_ends_the_task_and_warns(monkeypatch):
    warned = []
    monkeypatch.setattr(browser, "_unconfirmed_order", lambda url: warned.append(url))
    browser._check_no_order(AT_CHECKOUT, lambda: (THANKS, "Thank you for your order"), None)
    context = safety.RiskyLabel("context", "click Continue")
    browser._check_no_order(AT_CHECKOUT, lambda: (THANKS, "Thank you for your order"), context)
    assert warned == [THANKS, THANKS]


def test_an_order_the_user_confirmed_is_not_a_surprise(monkeypatch):
    warned = []
    monkeypatch.setattr(browser, "_unconfirmed_order", lambda url: warned.append(url))
    purchase = safety.RiskyLabel("purchase", "Place order")
    browser._check_no_order(AT_CHECKOUT, lambda: (THANKS, "Thank you for your order"), purchase)
    assert warned == []
