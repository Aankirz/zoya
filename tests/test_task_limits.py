"""Money path (D37): the per-task cost cap and step cap must stop a runaway orchestrator."""

from types import SimpleNamespace

import pytest

from zoya.config import MAX_TOOL_CALLS_PER_TASK
from zoya.orchestrator import TaskLimitExceeded, TaskLimits, task_cost_usd


def _event(input_tokens: int, output_tokens: int) -> SimpleNamespace:
    usage = {"inputTokens": input_tokens, "outputTokens": output_tokens}
    return SimpleNamespace(
        agent=SimpleNamespace(event_loop_metrics=SimpleNamespace(accumulated_usage=usage))
    )


def test_cost_uses_per_million_prices():
    assert task_cost_usd("gpt-5.6-terra", 1_000_000, 100_000) == pytest.approx(2.00 + 1.20)


def test_unknown_model_is_priced_at_the_most_expensive_rate():
    assert task_cost_usd("mystery-model", 1_000_000, 0) >= task_cost_usd(
        "gpt-5.6-terra", 1_000_000, 0
    )


def test_model_call_blocked_once_cost_cap_reached():
    limits = TaskLimits("gpt-5.6-terra", cost_cap_usd=0.50)

    with pytest.raises(TaskLimitExceeded):
        limits._check_limits(_event(input_tokens=200_000, output_tokens=10_000))  # $0.52


def test_model_call_allowed_under_cost_cap():
    limits = TaskLimits("gpt-5.6-terra", cost_cap_usd=0.50)

    limits._check_limits(_event(input_tokens=10_000, output_tokens=1_000))


def test_model_call_blocked_after_max_tool_calls():
    limits = TaskLimits("gpt-5.6-terra")
    for _ in range(MAX_TOOL_CALLS_PER_TASK):
        limits._count_tool_call(None)

    with pytest.raises(TaskLimitExceeded):
        limits._check_limits(_event(0, 0))
