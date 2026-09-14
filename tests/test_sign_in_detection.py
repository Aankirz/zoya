"""Sign-in detection (D37: the handoff decision). Owner's run 2026-09-15: every Spotify song
said "sign in first" while signed in, because an invisible reCAPTCHA badge iframe counted as a
CAPTCHA. The iframe tag is the one captured from open.spotify.com that night (query cut); the
badge had no bounding box there, stood in for here by visibility:hidden.
Headless Chrome, so Playwright's own visibility rules are what's tested."""

import pytest

from zoya.skills.spotify_web import actions as spotify
from zoya.tools import browser

BADGE = (
    '<div class="grecaptcha-badge" style="visibility:hidden">'
    '<div class="grecaptcha-logo"><iframe title="reCAPTCHA" width="256" height="60" '
    'src="https://www.google.com/recaptcha/enterprise/anchor"></iframe></div></div>'
)
SIGNED_IN_HEADER = '<button data-testid="user-widget-link" aria-label="Ankit">A</button>'
SIGNED_OUT_HEADER = '<button data-testid="login-button">Log in</button>'
VISIBLE_CAPTCHA = '<iframe title="recaptcha challenge expires in two minutes" src="about:blank">'
PASSWORD = '<form><input type="password" name="password"></form>'
# The rows Spotify listed for "Loser" on the signed-in profile (probe, 2026-09-15).
LOSER_ROWS = [
    "Play Loser by Tame Impala",
    "Play Sunflower - Spider-Man: Into the Spider-Verse by Post Malone, Swae Lee",
    "Play Loser by Tame Impala",
    "Play Dracula by Tame Impala",
    "Play Loser by Dino James",
]


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


@pytest.mark.parametrize(
    ("body", "wall"),
    [
        (BADGE + SIGNED_IN_HEADER, ""),
        (BADGE + VISIBLE_CAPTCHA, "captcha"),
        (PASSWORD, "password"),
    ],
)
def test_only_a_visible_password_or_captcha_is_a_wall(page, body, wall):
    page.set_content(body)
    assert browser.sign_in_wall(page) == wall


@pytest.mark.parametrize(
    ("body", "needed"),
    [
        (BADGE + SIGNED_IN_HEADER, False),
        (BADGE + SIGNED_OUT_HEADER, True),
    ],
)
def test_spotify_asks_for_sign_in_only_on_the_log_in_button(page, body, needed):
    page.set_content(body)
    assert spotify.needs_sign_in(page) is needed


def test_spotify_not_sure_means_try_the_song(page, monkeypatch):
    monkeypatch.setattr(spotify, "WAIT_MS", 200)
    page.set_content(BADGE)
    assert spotify.needs_sign_in(page) is False


def test_pick_track_plays_the_tame_impala_loser():
    assert spotify.pick_track("Loser", "Tame Impala", LOSER_ROWS) == 0
    assert spotify.pick_track("Loser", "Dino James", LOSER_ROWS) == 4
