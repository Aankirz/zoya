"""Loading harness runs."""

from pathlib import Path

import pytest

from evals.autotune import score

FIXTURES = Path(__file__).parent / "fixtures"


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
