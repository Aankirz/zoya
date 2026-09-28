"""Enter in a field is checked by Guard 2 as the click on its form's default button, unchanged."""

import pytest

from zoya import safety
from zoya.tools import browser

ALLOWED = {
    "a search form's Search button": (
        '<form action="/results"><input name="q"><button aria-label="Search">' "</button></form>"
    ),
    "a GET search form's Go button": (
        '<form method="get"><input type="search">' '<input type="submit" value="Go"></form>'
    ),
}
REFUSED = {
    "a form whose button places an order": (
        '<form><input name="q"><button>Place order</button>' "</form>"
    ),
    "a POST form's Go button": (
        '<form method="post"><input type="search">' "<button>Go</button></form>"
    ),
    "a message form's Send button": (
        '<form><textarea name="m"></textarea>' "<button>Send</button></form>"
    ),
}
NO_BUTTON = {
    "a search field in a form with no submit button": (
        '<form action="/results"><input aria-label="Search" name="q"></form>'
        "<button>Search</button>",
        False,
    ),
    "an unnamed field in a form with no submit button": ('<form><input name="q"></form>', True),
    "a message field in a form with only a plain button": (
        '<form><input aria-label="Message"><button type="button">Send</button></form>',
        True,
    ),
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


def target(page, body):
    page.set_content(body)
    return browser.enter_target(page, page.locator("input, textarea").first)


@pytest.mark.parametrize("body", ALLOWED.values(), ids=ALLOWED.keys())
def test_enter_is_free_where_clicking_the_default_button_is(page, body):
    assert safety.click_risk(target(page, body).facts) is None


@pytest.mark.parametrize("body", REFUSED.values(), ids=REFUSED.keys())
def test_enter_asks_where_clicking_the_default_button_would(page, body):
    assert safety.click_risk(target(page, body).facts) is not None


@pytest.mark.parametrize(("body", "asks"), NO_BUTTON.values(), ids=NO_BUTTON.keys())
def test_without_a_submit_button_the_field_itself_is_checked_as_the_submit(page, body, asks):
    checked = target(page, body)
    assert checked.facts.is_submit and (safety.click_risk(checked.facts) is not None) is asks


def test_a_field_outside_any_form_never_gets_enter(page):
    assert target(page, '<input aria-label="Search">') is None
