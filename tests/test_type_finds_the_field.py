"""browser_type types into a field: a button or link sharing the field's name never wins."""

import pytest

from zoya.tools import browser

PAGES = {
    "search box beside a Search link": """
        <a href="#">Search</a>
        <input type="text" role="searchbox" aria-label="Search Amazon.in">""",
    "combobox beside a Search button": """
        <button>Search</button>
        <input role="combobox" aria-label="Search" aria-expanded="false">""",
    "field named by placeholder beside a Search button": """
        <button>Search</button>
        <input type="search" placeholder="Search">""",
    "rich editor named by its label": """
        <button>Post</button>
        <div contenteditable="true" role="textbox" aria-label="Post text"></div>""",
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


@pytest.mark.parametrize("body", PAGES.values(), ids=PAGES.keys())
def test_typing_finds_the_field_not_a_same_named_control(page, body):
    page.set_content(body)
    field = "Post text" if "Post text" in body else "Search"
    found = browser._locate_field(page, field)
    found.fill("wireless mouse")
    assert found.evaluate("e => e.value ?? e.textContent") == "wireless mouse"


def test_a_page_with_no_such_field_says_so(page):
    page.set_content("<button>Search</button>")
    with pytest.raises(browser.ToolError, match="can't find"):
        browser._locate_field(page, "Search")
