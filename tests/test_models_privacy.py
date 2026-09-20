"""D36: every OpenAI request must be sent with store=False.

Fails loudly if zoya/models.py ever builds an OpenAI config that could store
data server-side (STACK §3, docs/DECISIONS.md D36).
"""

from types import SimpleNamespace

import pytest

from zoya.config import BRAIN_PLANNING_REASONING_EFFORT, BRAIN_STEP_REASONING_EFFORT
from zoya.models import brain_planning_model, get_model
from zoya.orchestrator import ReasoningSchedule

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


def test_planning_model_puts_store_false_in_the_request_body():
    model = brain_planning_model()
    request = model._format_request([{"role": "user", "content": [{"text": "hi"}]}])

    assert request["store"] is False, "the Responses API stores requests unless told not to"


def test_planning_model_never_sets_stateful_true():
    assert brain_planning_model().get_config().get("stateful") is not True


def test_planning_model_reasons_and_still_takes_function_tools():
    model = brain_planning_model()
    tool_spec = {
        "name": "open_app",
        "description": "Open an app",
        "inputSchema": {"json": {"type": "object", "properties": {}}},
    }
    request = model._format_request([{"role": "user", "content": [{"text": "hi"}]}], [tool_spec])

    assert request["reasoning"] == {"effort": BRAIN_PLANNING_REASONING_EFFORT}
    assert [tool["name"] for tool in request["tools"]] == ["open_app"]


def test_reasoning_is_dropped_after_the_planning_call():
    model = brain_planning_model()
    schedule = ReasoningSchedule()
    event = SimpleNamespace(agent=SimpleNamespace(model=model))

    schedule._drop_reasoning_after_plan(event)
    assert model.get_config()["params"]["reasoning"]["effort"] == BRAIN_PLANNING_REASONING_EFFORT

    schedule._drop_reasoning_after_plan(event)
    schedule._drop_reasoning_after_plan(event)
    effort = model.get_config()["params"]["reasoning"]["effort"]
    assert effort == BRAIN_STEP_REASONING_EFFORT
    assert model._format_request([{"role": "user", "content": [{"text": "hi"}]}])["store"] is False
