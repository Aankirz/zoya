from pathlib import Path

import pytest

# evals/autotune never imports zoya (the app is macOS-only), so its tests must run where zoya
# cannot be imported.
ZOYA_FREE_DIR = Path(__file__).parent / "autotune"


def _zoya_free(request: pytest.FixtureRequest) -> bool:
    return request.node.path.is_relative_to(ZOYA_FREE_DIR)


@pytest.fixture(autouse=True)
def no_keychain_license(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if _zoya_free(request):
        return
    from zoya import config

    monkeypatch.setattr(config, "_keychain_license", lambda: "")


@pytest.fixture(autouse=True)
def no_page_read_after_clicks(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    if _zoya_free(request):
        return
    from zoya.tools import browser

    monkeypatch.setattr(browser, "_playwright_url_and_text", lambda: ("", ""))
    monkeypatch.setattr(browser, "_ref_url_and_text", lambda: ("", ""))
    monkeypatch.setattr(browser, "ACTION_SETTLE_S", 0)
