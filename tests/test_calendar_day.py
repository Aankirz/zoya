"""D141: a day picked in a date calendar is not a checkout; real checkouts still ask."""

import pytest

from zoya import safety
from zoya.tools import browser


def day(labels, role="gridcell", container="Check-out date", submit=False, link=False):
    return safety.ClickFacts(
        labels=labels,
        role=role,
        is_submit=submit,
        is_link=link,
        host="stay.example",
        date_container=container,
    )


@pytest.mark.parametrize(
    "clicked",
    [
        day(["17", "17 October 2026, check-out date"]),
        day(["Fri 17 Oct 2026 check out"], role="button", container="Select your dates"),
        day(["October 17, 2026 (selected) checkout"], role="td", container="Calendar"),
    ],
)
def test_a_day_in_a_date_calendar_no_longer_asks(clicked):
    assert safety.click_risk(clicked) is None


@pytest.mark.parametrize(
    ("why", "clicked"),
    [
        ("a Check out button in the date dialog", day(["Check out"], role="button")),
        ("Proceed to checkout", day(["Proceed to checkout"], role="button")),
        ("a label that is not only a date", day(["17", "Check out now"])),
        ("a grid with no date word", day(["17 check out"], container="Your order")),
        ("no container at all", day(["17 check out"], container="")),
        ("a submit", day(["17 check out"], role="button", submit=True)),
        ("a link", day(["17 check out"], role="link", link=True)),
        ("an unexpected role", day(["17 check out"], role="checkbox")),
    ],
)
def test_every_real_checkout_still_asks(why, clicked):
    assert safety.click_risk(clicked) is not None, why


PAGES = {
    "grid labelled by aria-label": (
        '<div role="grid" aria-label="Check-out date"><span role="gridcell" id="t">17</span></div>',
        "Check-out date",
    ),
    "dialog labelled by a heading": (
        '<div role="dialog" aria-labelledby="h"><h2 id="h">Select dates</h2>'
        '<button id="t">17</button></div>',
        "Select dates",
    ),
    "table with a caption": (
        '<table><caption>Calendar</caption><tr><td id="t">17</td></tr></table>',
        "Calendar",
    ),
    "no calendar around it": ('<div><button id="t">17</button></div>', ""),
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


@pytest.mark.parametrize(("body", "label"), PAGES.values(), ids=PAGES.keys())
def test_the_page_fact_reads_the_calendar_label(page, body, label):
    page.set_content(body)
    assert page.locator("#t").evaluate(browser.ELEMENT_SHAPE_JS)["dateContainer"] == label
