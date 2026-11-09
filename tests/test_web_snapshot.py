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


CONSENT_FRAME = """
    <button>Search</button>
    <iframe style="position:fixed;inset:0;width:100%;height:100%;border:0"
      srcdoc="<p>We use cookies</p><button onclick='parent.postMessage(1, &quot;*&quot;)'>Accept
      </button>"></iframe>
    <script>addEventListener('message', () => document.title = 'accepted')</script>"""


@pytest.fixture(scope="module")
def playwright():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as running:
        yield running


@pytest.fixture(scope="module")
def page(playwright):
    from playwright.sync_api import Error

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


def test_a_frame_drawn_over_the_page_is_read_and_its_control_resolves(
    page, playwright, monkeypatch
):
    monkeypatch.setattr(
        web_loop.browser,
        "use_test_id_attribute",
        lambda name: playwright.selectors.set_test_id_attribute(name),
    )
    page.set_content(CONSENT_FRAME)
    page.wait_for_function("document.querySelector('iframe').contentDocument?.body?.innerText")
    observed = web_loop._observe_on(page)
    offered = {a["label"].strip(): a for a in observed["actions"]}
    assert "Search" not in offered and "We use cookies" in observed["text"]
    accept = offered["Accept"]
    assert accept["node"] > web_loop.FRAME_NODE_STRIDE
    web_loop.locate(page, observed, accept).click()
    page.wait_for_function("document.title === 'accepted'")
