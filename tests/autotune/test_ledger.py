"""The autotune ledger TSV and its per-night spend."""

from pathlib import Path

import pytest

from evals.autotune.ledger import COLUMNS, Ledger


def row(**overrides: object) -> dict:
    return {
        "night": "2026-09-30",
        "sha": "3f2a9c1",
        "task": "imdb-search",
        "group": "no-code site",
        "success": 1,
        "cents": 1.2,
        "seconds": 41.5,
        "cause": "pass",
    } | overrides


def test_a_missing_ledger_is_empty(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "history.tsv")
    assert ledger.rows() == []
    assert ledger.spent_cents("2026-09-30") == 0


def test_append_writes_a_header_then_rows(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "autotune" / "history.tsv"
    ledger = Ledger(path)
    ledger.append(row(utc="2026-09-30T01:00:00Z"))
    ledger.append(row(task="boat-buy", success=0, cause="never-reached-gate"))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "\t".join(COLUMNS)
    assert lines[1] == (
        "2026-09-30T01:00:00Z\t2026-09-30\t3f2a9c1\timdb-search\tno-code site\t1\t1.2\t41.5\tpass"
    )
    assert len(lines) == 3


def test_rows_read_back_as_strings(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "history.tsv")
    ledger.append(row())
    (read,) = ledger.rows()
    assert set(read) == set(COLUMNS)
    assert read["cents"] == "1.2" and read["success"] == "1"
    assert read["utc"].endswith("Z")


def test_spent_cents_counts_one_night_only(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "history.tsv")
    for night, cents in (("2026-09-29", 900), ("2026-09-30", 1.5), ("2026-09-30", 0.5)):
        ledger.append(row(night=night, cents=cents))
    assert ledger.spent_cents("2026-09-30") == pytest.approx(2.0)
    assert Ledger(tmp_path / "history.tsv").spent_cents("2026-09-29") == pytest.approx(900)
    assert ledger.spent_cents("2026-10-01") == 0


def test_other_columns_serve_other_tables(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "queue.tsv", ("utc", "branch", "sha"))
    ledger.append({"branch": "autotune/fix-search", "sha": "abc"})
    assert ledger.rows()[0]["branch"] == "autotune/fix-search"


def test_a_cause_with_tabs_and_newlines_stays_one_row(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "history.tsv")
    ledger.append(row(cause='say "stop"\tthen\nwait'))
    ledger.append(row(task="boat-buy"))
    rows = ledger.rows()
    assert [r["task"] for r in rows] == ["imdb-search", "boat-buy"]
    assert rows[0]["cause"] == 'say "stop" then wait'


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (row(extra=1), "unknown ledger columns: extra"),
        ({k: v for k, v in row().items() if k != "cause"}, "missing ledger columns: cause"),
    ],
)
def test_append_rejects_the_wrong_columns(bad: dict, message: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=message):
        Ledger(tmp_path / "history.tsv").append(bad)


def test_append_rejects_cents_that_are_not_a_number(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "history.tsv")
    with pytest.raises(ValueError):
        ledger.append(row(cents="a lot"))
    assert ledger.rows() == []


def test_a_foreign_file_is_never_appended_to(tmp_path: Path) -> None:
    path = tmp_path / "history.tsv"
    path.write_text("something\telse\n", encoding="utf-8")
    ledger = Ledger(path)
    with pytest.raises(ValueError, match="unexpected header"):
        ledger.append(row())
    with pytest.raises(ValueError, match="unexpected header"):
        ledger.rows()
    assert path.read_text(encoding="utf-8") == "something\telse\n"
