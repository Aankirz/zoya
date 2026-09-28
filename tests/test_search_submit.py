"""D138 (a): a GET search submit is D75 "navigate" only when every strict condition holds."""

import pytest

from zoya import safety
from zoya.tools import browser


def facts(name: str, search_form: bool = True, path: str = "/", submit: bool = True):
    return safety.ClickFacts(
        labels=[name],
        is_submit=submit,
        path=path,
        host="shop.example",
        role="button",
        search_form=search_form,
    )


@pytest.mark.parametrize("name", ["Go", "OK", "→"])
def test_a_get_search_submit_no_longer_asks(name):
    assert safety.click_risk(facts(name)) is None
    assert safety.reversible_click(facts(name)).undo == "go back"


@pytest.mark.parametrize(
    ("why", "clicked"),
    [
        ("a POST form or a GET form without a search field", facts("Go", search_form=False)),
        ("a risky name: order", facts("Order now")),
        ("a risky name: pay", facts("Pay")),
        ("a risky name: buy", facts("Buy")),
        ("a risky name: checkout", facts("Checkout")),
        ("a risky name: delete", facts("Delete")),
        ("a risky name: send", facts("Send")),
        ("a risky name: post", facts("Post")),
        ("a risky name: subscribe", facts("Subscribe")),
        ("a risky name: confirm", facts("Confirm")),
        ("a cart path", facts("Go", path="/cart/view")),
        ("a checkout path", facts("Go", path="/checkout")),
        ("a payment path", facts("Go", path="/payment/step2")),
    ],
)
def test_every_other_submit_still_asks(why, clicked):
    assert safety.click_risk(clicked) is not None, why


def test_the_rule_is_for_submits_only():
    assert safety.reversible_click(facts("Go", submit=False)) is None


PAGES = {
    "GET form with a searchbox": (
        '<form method="get"><input role="searchbox"><button>Go</button>',
        True,
    ),
    "form with no method holds a search input": (
        '<form><input type="search"><button>Go</button>',
        True,
    ),
    "POST form with a search input": (
        '<form method="post"><input type="search"><button>Go</button>',
        False,
    ),
    "GET form with a plain text field": (
        '<form method="get"><input type="text"><button>Go</button>',
        False,
    ),
    "no form at all": ('<input type="search"><button>Go</button>', False),
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


@pytest.mark.parametrize(("body", "expected"), PAGES.values(), ids=PAGES.keys())
def test_the_page_fact_reads_the_real_form(page, body, expected):
    page.set_content(body)
    shape = page.locator("button").evaluate(browser.ELEMENT_SHAPE_JS)
    assert shape["searchForm"] is expected
