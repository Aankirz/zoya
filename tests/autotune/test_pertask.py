"""The v2 per-task verdict and branch guard, on night 1's per-task counts (2026-09-29)."""

from evals.autotune import pertask
from evals.autotune.pertask import FAIL, FLAKY, PASS, UNKNOWN, Outcome


def runs(passes: int, total: int, cents: float = 1.0) -> list[Outcome]:
    return [Outcome(i < passes, cents) for i in range(total)]


NIGHT_1 = {
    "flipkart-search": runs(0, 18),
    "goodreads-search": runs(0, 18),
    "imdb-search": runs(1, 18),
    "boat-buy": runs(0, 18),
    "boat-newsletter": runs(3, 18),
    "wikipedia-open": runs(13, 18),
    "imdb-open": runs(16, 18),
    "ebay-search": runs(16, 18),
    "bandcamp-search": runs(18, 18),
    "boat-price": runs(18, 18),
}


def test_night_1_classifies_as_mostly_deterministic() -> None:
    states = {task: pertask.classify(history) for task, history in NIGHT_1.items()}
    assert [t for t, s in states.items() if s == FLAKY] == ["wikipedia-open"]
    assert states["imdb-open"] == states["bandcamp-search"] == PASS
    assert states["boat-newsletter"] == states["imdb-search"] == FAIL
    assert pertask.classify(runs(1, 2)) == UNKNOWN


def sentinel(**overrides: list[Outcome]) -> dict[str, list[Outcome]]:
    """One run per task at its usual outcome, with some tasks replaced."""
    usual = {t: [Outcome(pertask.classify(h) == PASS)] for t, h in NIGHT_1.items()}
    return {**usual, **overrides}


def test_a_fix_for_two_failing_tasks_is_recommended() -> None:
    candidate = sentinel(**{"flipkart-search": runs(3, 3), "boat-buy": runs(2, 3)})
    keep, reason = pertask.verdict(NIGHT_1, candidate)
    assert keep, reason
    assert "['boat-buy', 'flipkart-search']" in reason


def test_one_lucky_pass_is_not_a_fix() -> None:
    keep, reason = pertask.verdict(NIGHT_1, sentinel(**{"boat-newsletter": runs(1, 3)}))
    assert not keep and "fixes no failing task" in reason


def test_a_failed_sentinel_asks_for_reruns_before_any_verdict() -> None:
    candidate = sentinel(**{"flipkart-search": runs(3, 3), "boat-price": runs(0, 1)})
    assert pertask.reruns(NIGHT_1, candidate) == ["boat-price"]
    keep, reason = pertask.verdict(NIGHT_1, candidate)
    assert not keep and "run these again" in reason


def test_a_confirmed_regression_blocks_a_fix() -> None:
    candidate = sentinel(**{"flipkart-search": runs(3, 3), "boat-price": runs(1, 3)})
    keep, reason = pertask.verdict(NIGHT_1, candidate)
    assert not keep and "breaks a passing task" in reason


def test_one_sentinel_miss_that_reruns_clean_is_noise() -> None:
    candidate = sentinel(**{"flipkart-search": runs(3, 3), "imdb-open": [Outcome(True)] * 2})
    candidate["imdb-open"].insert(0, Outcome(False))
    keep, reason = pertask.verdict(NIGHT_1, candidate)
    assert keep, reason


def test_a_fix_that_costs_much_more_on_passing_tasks_is_not_recommended() -> None:
    pricey = {t: [Outcome(True, 2.0)] for t, h in NIGHT_1.items() if pertask.classify(h) == PASS}
    candidate = sentinel(**pricey, **{"flipkart-search": runs(3, 3)})
    keep, reason = pertask.verdict(NIGHT_1, candidate)
    assert not keep and "cents" in reason


def diff(path: str, *lines: str) -> str:
    return "\n".join(
        [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}", "@@ -1,1 +1,1 @@"]
        + list(lines)
    )


def test_a_generic_browser_fix_passes_the_guard() -> None:
    assert pertask.guard_branch(diff("zoya/tools/browser.py", "-a = 1", "+a = 2")) == ([], [])


def test_gate_tests_are_append_only() -> None:
    ok = diff("tests/test_safety.py", "+def test_new() -> None: ...")
    assert pertask.guard_branch(ok) == ([], [])
    bad = diff("tests/test_safety.py", "-    assert asks('Place order')")
    assert pertask.guard_branch(bad)[0]


def test_protected_constants_prompt_lines_and_the_judge_are_refused() -> None:
    for patch in (
        diff("zoya/config.py", "-JEV_STEP_CONFIDENCE = 0.70", "+JEV_STEP_CONFIDENCE = 0.60"),
        diff("zoya/prompts.py", "-Always confirm first.", "+Just do it."),
        diff("evals/harness/run.py", "-    meter.channel.reply('cancel', t)", "+    pass"),
        diff("evals/autotune/pertask.py", "-MIN_SAMPLES = 3", "+MIN_SAMPLES = 1"),
        diff("evals/harness/tasks.json", '-  "stakes": "money",'),
    ):
        assert pertask.guard_branch(patch)[0], patch


def test_product_and_grading_never_change_together() -> None:
    both = diff("zoya/tools/fast.py", "+x = 1") + "\n" + diff("evals/harness/tasks.json", "+ {}")
    violations, _ = pertask.guard_branch(both)
    assert any("split the branch" in v for v in violations)


def test_a_gate_change_is_flagged_for_the_owner() -> None:
    violations, flags = pertask.guard_branch(diff("zoya/safety.py", "-x = 1", "+x = 2"))
    assert violations == [] and flags
