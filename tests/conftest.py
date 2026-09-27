import pytest

from zoya import config


@pytest.fixture(autouse=True)
def no_keychain_license(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_keychain_license", lambda: "")


@pytest.fixture(autouse=True)
def no_page_read_after_clicks(monkeypatch: pytest.MonkeyPatch) -> None:
    from zoya.tools import browser

    monkeypatch.setattr(browser, "_playwright_url_and_text", lambda: ("", ""))
    monkeypatch.setattr(browser, "_ref_url_and_text", lambda: ("", ""))
    monkeypatch.setattr(browser, "ACTION_SETTLE_S", 0)
