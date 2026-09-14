"""D36: every OpenAI request must be sent with store=False.

Fails loudly if zoya/models.py ever builds an OpenAI config that could store
data server-side (STACK §3, docs/DECISIONS.md D36).
"""

import pytest

from zoya.models import get_model

ROLES = ["brain", "vision", "router"]


@pytest.fixture(autouse=True)
def _openai_env(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("BRAIN_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("VISION_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("ROUTER_MODEL", "gpt-5.6-luna")


@pytest.mark.parametrize("role", ROLES)
def test_openai_model_sets_store_false(role):
    model = get_model(role, provider="openai")
    config = model.get_config()

    assert (
        "params" in config
    ), f"{role}: OpenAI config has no params — store=False can't be enforced"
    assert config["params"].get("store") is False, f"{role}: OpenAI config may store request data"


@pytest.mark.parametrize("role", ROLES)
def test_openai_model_never_sets_stateful_true(role):
    model = get_model(role, provider="openai")
    config = model.get_config()

    assert config.get("stateful") is not True, f"{role}: stateful=True defeats store=False"


def test_missing_model_id_raises(monkeypatch):
    monkeypatch.delenv("BRAIN_MODEL", raising=False)
    with pytest.raises(RuntimeError):
        get_model("brain", provider="openai")


def test_unknown_provider_raises(monkeypatch):
    with pytest.raises(ValueError):
        get_model("brain", provider="anthropic-direct")
