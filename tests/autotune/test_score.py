"""Scoring harness runs and the keep-or-discard decision, on noisy synthetic repeats."""

import json
from pathlib import Path

import pytest

from evals.autotune import score

FIXTURES = Path(__file__).parent / "fixtures"


def summaries(*names: str) -> list[dict]:
    return [score.summarize(score.load(FIXTURES / f"{name}.json")) for name in names]


BASELINE = ("baseline_1", "baseline_2", "baseline_3")


def test_load_reads_a_harness_run() -> None:
    runs = score.load(FIXTURES / "baseline_1.json")
    assert len(runs) == 8
    assert set(runs[0]) >= {"id", "group", "success", "seconds", "cents", "steps", "error"}


@pytest.mark.parametrize("content", ['{"id": "x"}', "[1, 2]", "not json"])
def test_load_rejects_anything_but_a_list_of_objects(content: str, tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        score.load(path)


def test_summarize() -> None:
    (summary,) = summaries("baseline_1")
    assert summary == {
        "success": 5,
        "total": 8,
        "by_group": {"no-code site": [2, 3], "former skill": [2, 3], "mac app": [1, 2]},
        "median_seconds": pytest.approx(62.5),
        "cents": pytest.approx(24.0),
    }


def test_summarize_counts_only_true_as_success() -> None:
    runs = [
        {"id": "a", "group": "mac app", "success": True, "seconds": 1.0, "cents": 1.0},
        {"id": "b", "group": "mac app", "success": "yes", "seconds": 3.0, "cents": 1.0},
    ]
    assert score.summarize(runs)["success"] == 1


def test_summarize_an_empty_run() -> None:
    assert score.summarize([]) == {
        "success": 0,
        "total": 0,
        "by_group": {},
        "median_seconds": 0.0,
        "cents": 0,
    }


def test_a_real_gain_is_kept() -> None:
    keep, reason = score.decide(summaries(*BASELINE), summaries("better_1", "better_2"))
    assert keep, reason
    assert "4.67 → 6.50" in reason


def test_noise_is_not_a_gain() -> None:
    # Each noise repeat happens to beat one baseline repeat, but the means differ by 0.33.
    keep, reason = score.decide(summaries(*BASELINE), summaries("noise_1", "noise_2"))
    assert not keep
    assert "gains less than 1" in reason


def test_noise_that_clears_a_small_min_gain_still_fails_on_a_group() -> None:
    keep, reason = score.decide(summaries(*BASELINE), summaries("noise_1", "noise_2"), min_gain=0.3)
    assert not keep
    assert "former skill drops from 1.67 to 1.50" in reason


def test_a_group_drop_is_discarded_despite_a_higher_total() -> None:
    keep, reason = score.decide(summaries(*BASELINE), summaries("group_drop_1", "group_drop_2"))
    assert not keep
    assert "mac app drops from 1.00 to 0.50" in reason


def test_a_candidate_more_than_15_percent_dearer_per_success_is_discarded() -> None:
    keep, reason = score.decide(summaries(*BASELINE), summaries("costly_1", "costly_2"))
    assert not keep
    assert "cents per success" in reason


def test_cost_at_exactly_15_percent_worse_is_kept() -> None:
    base = [_summary(4, 40.0), _summary(4, 40.0)]
    cand = [_summary(6, 69.0), _summary(6, 69.0)]  # 10.00 → 11.50 cents per success
    assert score.decide(base, cand)[0]
    cand = [_summary(6, 69.1), _summary(6, 69.1)]
    assert not score.decide(base, cand)[0]


def test_gain_exactly_min_gain_is_kept() -> None:
    base = [_summary(4, 10.0), _summary(5, 10.0)]
    cand = [_summary(5, 10.0), _summary(6, 10.0)]
    assert score.decide(base, cand)[0]
    assert not score.decide(base, cand, min_gain=1.01)[0]


def test_a_single_run_is_not_enough() -> None:
    keep, reason = score.decide(summaries(*BASELINE), summaries("better_1"))
    assert not keep
    assert "at least 2" in reason
    assert not score.decide(summaries("baseline_1"), summaries("better_1", "better_2"))[0]


def test_runs_over_different_tasks_are_not_compared() -> None:
    keep, reason = score.decide(summaries(*BASELINE), summaries("better_1", "fewer_tasks"))
    assert not keep
    assert "same tasks" in reason


def test_a_baseline_with_no_successes_puts_no_cap_on_cost() -> None:
    base = [_summary(0, 10.0), _summary(0, 10.0)]
    keep, reason = score.decide(base, [_summary(2, 50.0), _summary(2, 50.0)])
    assert keep, reason


def test_decide_accepts_summaries_loaded_back_from_json(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(summaries(*BASELINE)), encoding="utf-8")
    baseline = json.loads(path.read_text(encoding="utf-8"))
    assert score.decide(baseline, summaries("better_1", "better_2"))[0]


def _summary(success: int, cents: float, total: int = 8) -> dict:
    return {
        "success": success,
        "total": total,
        "by_group": {"mac app": [success, total]},
        "median_seconds": 30.0,
        "cents": cents,
    }
