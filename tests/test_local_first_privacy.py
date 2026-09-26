"""Production P2 privacy: Supermemory local and Polly through the relay (D36, D37)."""

from __future__ import annotations

import io

import pytest

from zoya import memory_server, speech

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


def test_memory_server_gets_the_relay_and_license_and_no_provider_key(
    licensed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-byo")
    for name in BYO_KEYS:
        monkeypatch.setenv(name, "secret")
    env = memory_server.server_env()
    assert env["OPENAI_API_KEY"] == LICENSE
    assert env["OPENAI_BASE_URL"] == "https://relay.example/v1"
    assert not set(BYO_KEYS) & set(env)
    assert "sk-byo" not in env.values()


def test_memory_server_telemetry_is_always_off(licensed: None) -> None:
    assert memory_server.server_env()["SUPERMEMORY_DISABLE_TELEMETRY"] == "1"


def test_memory_server_log_never_holds_a_key(tmp_path) -> None:  # noqa: ANN001
    log = tmp_path / "supermemory.log"
    printed = io.BytesIO(f"api key sm_AbC123xyz\nOPENAI_API_KEY={LICENSE}\nready\n".encode())
    memory_server._copy_redacted(printed, log)
    text = log.read_text()
    assert "sm_AbC123xyz" not in text and LICENSE not in text and "ready" in text


def test_license_key_is_never_sent_to_a_plain_http_relay(
    licensed: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZOYA_RELAY_URL", "http://relay.example")
    sent = []
    monkeypatch.setattr(speech.urllib.request, "urlopen", lambda *a, **k: sent.append(a))
    with pytest.raises(RuntimeError):
        next(speech._relay_polly_chunks("Notes is open."))
    assert not sent


def test_without_a_license_memory_and_voice_are_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZOYA_LICENSE_KEY", raising=False)
    assert not memory_server.wanted()
    assert [name for name, _ in speech._engines()] == ["polly", "elevenlabs"]
