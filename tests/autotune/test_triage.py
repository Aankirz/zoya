"""The v2 prototype: per-task history, failure causes and the paired keep rule, on runs shaped
like night 1 (2026-09-29): most tasks always pass or always fail, a few are flaky."""

import pytest

from evals.autotune import triage

# pass counts per 6 main runs, close to night 1's per-task rates over 18 runs
NIGHT_1 = {
    "flipkart-search": 0,
    "goodreads-search": 0,
    "boat-buy": 0,
    "boat-newsletter": 1,
    "wikipedia-open": 4,
    "imdb-open": 5,
    "ebay-search": 5,
    "bandcamp-search": 6,
    "boat-price": 6,
}


def run(task: str, success: bool, cents: float = 1.0, **fields) -> dict:
    return {"id": task, "group": "no-code site", "success": success, "cents": cents, **fields}


def main_history(passes: dict[str, int] = NIGHT_1, runs: int = 6) -> dict[str, list[dict]]:
    nights = [[run(task, i < n) for task, n in passes.items()] for i in range(runs)]
    return triage.history(nights)


def candidate(results: dict[str, list[bool]], cents: float = 1.0) -> dict[str, list[dict]]:
    return {task: [run(task, ok, cents) for ok in oks] for task, oks in results.items()}


def solid_canary(times: int = 1) -> dict[str, list[bool]]:
    return {"imdb-open": [True] * times, "bandcamp-search": [True] * times}


def test_history_keeps_the_newest_window_per_task() -> None:
    nights = [[run("a", i >= 2)] for i in range(triage.WINDOW + 2)]
    kept = triage.history(nights)["a"]
    assert len(kept) == triage.WINDOW
    assert all(r["success"] for r in kept)


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        ("flipkart-search", triage.BROKEN),
        ("boat-newsletter", triage.BROKEN),
        ("wikipedia-open", triage.FLAKY),
        ("imdb-open", triage.SOLID),
        ("boat-price", triage.SOLID),
    ],
)
def test_night_1_tasks_sort_into_solid_broken_and_flaky(task: str, expected: str) -> None:
    assert triage.state(main_history()[task]) == expected


def test_a_task_with_little_history_is_new() -> None:
    assert triage.state([run("a", True)] * (triage.MIN_HISTORY - 1)) == triage.NEW


@pytest.mark.parametrize(
    ("task", "failed", "expected"),
    [
        ({}, {"error": "over 300 s, stopped"}, "timeout"),
        ({}, {"error": "RuntimeError: boom"}, "crash"),
        ({}, {"confirmations": ["Submit search?"]}, "false-ask"),
        ({"stakes": "money"}, {"said": ["I couldn't reach the search box"]}, "never-reached-gate"),
        (
            {"stakes": "submit"},
            {"confirmations": ["Shall I enter the email?"], "failed_checks": ['{"confirm": "x"}']},
            "ask-wording",
        ),
        ({}, {"said": ["Goodreads is showing its sign-in page."]}, "wall"),
        ({}, {"failed_checks": ['{"url": "wikipedia"}']}, "wrong-page"),
        ({}, {"failed_checks": ['{"said": "Dune"}']}, "wrong-answer"),
    ],
)
def test_cause_reads_only_what_the_harness_recorded(
    task: dict, failed: dict, expected: str
) -> None:
    assert triage.cause(task, run("t", False, **failed)) == expected


def test_a_passing_run_has_no_cause() -> None:
    assert triage.cause({}, run("t", True)) == "pass"


def test_a_broken_target_passing_two_of_three_is_kept() -> None:
    cand = candidate({"flipkart-search": [True, True, False], **solid_canary()})
    verdict, reason = triage.decide(main_history(), cand, ["flipkart-search"])
    assert verdict == "keep", reason


def test_one_lucky_pass_is_not_a_fix() -> None:
    cand = candidate({"flipkart-search": [True, False, False], **solid_canary()})
    assert triage.decide(main_history(), cand, ["flipkart-search"])[0] == "discard"


def test_a_flaky_task_passing_is_not_a_fix() -> None:
    cand = candidate({"wikipedia-open": [True] * 3, **solid_canary()})
    assert triage.decide(main_history(), cand, ["wikipedia-open"])[0] == "discard"


def test_a_solid_task_failing_once_in_one_run_asks_for_a_rerun() -> None:
    cand = candidate({"flipkart-search": [True] * 3, "imdb-open": [False], "boat-price": [True]})
    verdict, reason = triage.decide(main_history(), cand, ["flipkart-search"])
    assert verdict == "rerun"
    assert "imdb-open" in reason


def test_a_solid_task_failing_twice_discards_even_with_a_fix() -> None:
    cand = candidate({"flipkart-search": [True] * 3, "imdb-open": [False, True, False]})
    assert triage.decide(main_history(), cand, ["flipkart-search"])[0] == "discard"


def test_one_failure_in_three_runs_of_a_solid_task_is_tolerated() -> None:
    cand = candidate({"flipkart-search": [True] * 3, "imdb-open": [True, False, True]})
    assert triage.decide(main_history(), cand, ["flipkart-search"])[0] == "keep"


def test_a_fix_that_makes_solid_tasks_much_dearer_is_discarded() -> None:
    cand = candidate({"flipkart-search": [True] * 3})
    cand.update(candidate(solid_canary(), cents=1.2))
    verdict, reason = triage.decide(main_history(), cand, ["flipkart-search"])
    assert verdict == "discard"
    assert "cents per run" in reason


def test_a_target_without_history_cannot_be_fixed() -> None:
    cand = candidate({"brand-new": [True] * 3, **solid_canary()})
    assert triage.decide(main_history(), cand, ["brand-new"])[0] == "discard"
