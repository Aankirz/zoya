import pytest

from zoya import config


@pytest.fixture(autouse=True)
def no_keychain_license(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_keychain_license", lambda: "")
