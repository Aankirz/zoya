"""The web loop's snapshot offers what a click can really reach: nothing under an overlay, and
controls inside open shadow roots. Headless Chrome, so the browser's own hit-testing is tested."""

import pytest

from zoya.agents import web_loop

COVERED = """
    <button style="position:absolute;top:20px;left:20px">Search</button>
    <div style="position:fixed;inset:0;background:white">
      <button style="position:absolute;top:300px;left:20px">Accept cookies</button>
    </div>"""
SHADOW = """
    <div id="host"></div>
    <script>
      const root = document.getElementById('host').attachShadow({mode: 'open'});
      root.innerHTML = '<input type="search" aria-label="Search the archive">' +
        '<button>Go</button><p>Shadow text</p>';
    </script>"""


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


def labels(page, body: str) -> set[str]:
    page.set_content(body)
    return {action["label"] for action in page.evaluate(web_loop.SNAPSHOT_JS)["actions"]}


def test_a_control_under_an_overlay_is_not_offered(page):
    offered = labels(page, COVERED)
    assert "Accept cookies" in offered and "Search" not in offered


def test_controls_inside_an_open_shadow_root_are_offered(page):
    assert {"Search the archive", "Go"} <= labels(page, SHADOW)
    assert "Shadow text" in page.evaluate(web_loop.SNAPSHOT_JS)["text"]
