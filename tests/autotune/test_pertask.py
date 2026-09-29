"""The per-task classes and keep rule, on history shaped like night 1 (2026-09-29)."""

from evals.autotune import pertask
from evals.autotune.pertask import (
    CONSISTENT,
    FAIL,
    FLAKY,
    NEW,
    NEW_FAIL,
    PASS,
    PROVEN,
    REJECTED,
    Outcome,
)


def runs(passes: int, total: int, cents: float = 1.0) -> list[Outcome]:
    return [Outcome(i < passes, cents) for i in range(total)]


def spread(passes: int, total: int = pertask.WINDOW) -> list[Outcome]:
    """`passes` successes as the last runs of `total`, so the window sees them."""
    return runs(0, total - passes) + runs(passes, passes)


NIGHT_1 = {
    "flipkart-search": spread(0),
    "goodreads-search": spread(0),
    "imdb-search": spread(0),
    "boat-buy": spread(0),
    "boat-newsletter": spread(1),
    "wikipedia-open": spread(4),
    "imdb-open": spread(5),
    "ebay-search": spread(5),
    "bandcamp-search": spread(6),
    "boat-price": spread(6),
}
HELD_OUT = {"bandcamp-search", "boat-price"}


def test_night_1_classifies_as_mostly_deterministic() -> None:
    states = {task: pertask.classify(history) for task, history in NIGHT_1.items()}
    assert [t for t, s in states.items() if s == FLAKY] == ["wikipedia-open"]
    assert states["imdb-open"] == states["bandcamp-search"] == PASS
    assert states["boat-newsletter"] == states["imdb-search"] == FAIL
    assert pertask.classify(runs(1, 2)) == NEW


def test_only_the_newest_window_counts() -> None:
    assert pertask.classify(runs(0, 10) + runs(6, 6)) == PASS
    assert pertask.classify(runs(10, 10) + runs(0, 6)) == FAIL


def test_a_pass_task_failing_tonight_is_the_new_fail_alarm() -> None:
    assert pertask.label(spread(6), [Outcome(False)]) == NEW_FAIL
    assert pertask.label(spread(6), [Outcome(True)]) == PASS
    assert pertask.label(spread(3), [Outcome(False)]) == FLAKY
    assert pertask.label([], [Outcome(False)]) == NEW


def sentinels(**overrides: list[Outcome]) -> dict[str, list[Outcome]]:
    """One run per task at its usual outcome, with some tasks replaced."""
    usual = {t: [Outcome(pertask.classify(h) == PASS)] for t, h in NIGHT_1.items()}
    return {**usual, **overrides}


def judge(candidate: dict[str, list[Outcome]], targets: list[str]) -> pertask.Verdict:
    return pertask.verdict(NIGHT_1, candidate, targets, HELD_OUT)


def test_a_fix_for_two_failing_tasks_is_proven() -> None:
    candidate = sentinels(**{"flipkart-search": runs(3, 3), "boat-buy": runs(2, 3)})
    result = judge(candidate, ["flipkart-search", "boat-buy"])
    assert result.status == PROVEN, result.reason
    assert result.fixed == ["boat-buy", "flipkart-search"]
    assert result.broken == []


def test_one_lucky_pass_is_not_a_fix() -> None:
    result = judge(sentinels(**{"boat-newsletter": runs(1, 3)}), ["boat-newsletter"])
    assert result.status == REJECTED and "fixes no target" in result.reason


def test_a_failing_task_that_is_not_a_target_does_not_count_as_fixed() -> None:
    result = judge(sentinels(**{"boat-buy": runs(3, 3), "flipkart-search": runs(0, 3)}), [])
    assert result.fixed == [] and result.status == REJECTED


def test_a_failed_sentinel_asks_for_reruns_before_any_verdict() -> None:
    candidate = sentinels(**{"flipkart-search": runs(3, 3), "imdb-open": runs(0, 1)})
    assert pertask.reruns(NIGHT_1, candidate) == ["imdb-open"]
    result = judge(candidate, ["flipkart-search"])
    assert result.status == REJECTED and "unfinished" in result.reason


def test_a_confirmed_regression_is_broken_and_blocks_a_fix() -> None:
    candidate = sentinels(**{"flipkart-search": runs(3, 3), "imdb-open": runs(1, 3)})
    result = judge(candidate, ["flipkart-search"])
    assert result.broken == ["imdb-open"]
    assert result.status == REJECTED and "breaks passing" in result.reason


def test_one_sentinel_miss_that_reruns_clean_is_noise() -> None:
    candidate = sentinels(**{"flipkart-search": runs(3, 3), "imdb-open": runs(2, 3)[::-1]})
    assert judge(candidate, ["flipkart-search"]).status == PROVEN


def test_a_broken_held_out_task_vetoes_a_proven_fix() -> None:
    candidate = sentinels(**{"flipkart-search": runs(3, 3), "boat-price": runs(1, 3)})
    result = judge(candidate, ["flipkart-search"])
    assert result.held_out_broken == ["boat-price"] and result.broken == []
    assert result.status == REJECTED and "held-out" in result.reason


def test_a_fix_that_costs_much_more_on_passing_tasks_is_rejected() -> None:
    pricey = {t: [Outcome(True, 2.0)] for t, h in NIGHT_1.items() if pertask.classify(h) == PASS}
    result = judge(sentinels(**pricey, **{"flipkart-search": runs(3, 3)}), ["flipkart-search"])
    assert result.status == REJECTED and "cents" in result.reason


def test_cents_within_the_ratio_still_prove() -> None:
    cheap = {t: [Outcome(True, 1.1)] for t, h in NIGHT_1.items() if pertask.classify(h) == PASS}
    result = judge(sentinels(**cheap, **{"flipkart-search": runs(3, 3)}), ["flipkart-search"])
    assert result.status == PROVEN, result.reason


def test_a_flaky_target_passing_every_run_is_consistent_not_proven() -> None:
    result = judge(sentinels(**{"wikipedia-open": runs(3, 3)}), ["wikipedia-open"])
    assert result.status == CONSISTENT and result.fixed == []


def test_a_flaky_target_that_misses_once_is_rejected() -> None:
    result = judge(sentinels(**{"wikipedia-open": runs(2, 3)}), ["wikipedia-open"])
    assert result.status == REJECTED


def test_flaky_sentinels_are_reported_not_judged_and_held_out_stays_quiet() -> None:
    history = {**NIGHT_1, "bandcamp-search": spread(3)}
    candidate = sentinels(**{"flipkart-search": runs(3, 3), "wikipedia-open": runs(0, 1)})
    candidate["bandcamp-search"] = runs(0, 1)
    result = pertask.verdict(history, candidate, ["flipkart-search"], HELD_OUT)
    assert result.status == PROVEN, result.reason
    assert result.not_judged == ["wikipedia-open 0/1"]


def test_a_target_without_its_three_runs_is_unfinished() -> None:
    result = judge(sentinels(**{"flipkart-search": runs(2, 2)}), ["flipkart-search"])
    assert result.status == REJECTED and "unfinished" in result.reason
