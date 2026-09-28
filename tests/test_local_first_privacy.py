"""Production P2 privacy: Polly through the relay (D36, D37)."""

from __future__ import annotations

import pytest

from zoya import speech

LICENSE = "zoya_live_license"
BYO_KEYS = (
    "SUPERMEMORY_API_KEY",
    "ELEVENLABS_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "FIREWORKS_API_KEY",
)


@pytest.fixture
def licensed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZOYA_LICENSE_KEY", LICENSE)
    monkeypatch.setenv("ZOYA_RELAY_URL", "https://relay.example")
    monkeypatch.setenv("ROUTER_MODEL", "gpt-5.6-luna")
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)


def test_license_key_is_never_sent_to_a_plain_http_relay(
    licensed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZOYA_RELAY_URL", "http://relay.example")
    sent = []
    monkeypatch.setattr(speech.urllib.request, "urlopen", lambda *a, **k: sent.append(a))
    with pytest.raises(RuntimeError):
        next(speech._relay_polly_chunks("Notes is open."))
    assert not sent


def test_without_a_license_voice_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZOYA_LICENSE_KEY", raising=False)
    assert [name for name, _ in speech._engines()] == ["polly", "elevenlabs"]
