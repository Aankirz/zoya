"""The autotune ledger TSV."""

from pathlib import Path

import pytest

from evals.autotune.ledger import COLUMNS, Ledger


def row(**overrides: object) -> dict:
    return {
        "exp_id": "exp-001",
        "description": "fewer jev steps",
        "patch_sha": "3f2a9c1",
        "success_mean": 6.5,
        "cents_total": 49.6,
        "seconds_median": 62.5,
        "verdict": "keep",
    } | overrides


def test_a_missing_ledger_is_empty(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.tsv")
    assert ledger.rows() == []
    assert ledger.spent_cents() == 0


def test_append_writes_a_header_then_rows(tmp_path: Path) -> None:
    path = tmp_path / "logs" / "autotune" / "ledger.tsv"
    ledger = Ledger(path)
    ledger.append(row(utc="2026-09-27T10:00:00Z"))
    ledger.append(row(exp_id="exp-002", cents_total=12, verdict="discard"))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "\t".join(COLUMNS)
    assert (
        lines[1] == "2026-09-27T10:00:00Z\texp-001\tfewer jev steps\t3f2a9c1\t6.5\t49.6\t62.5\tkeep"
    )
    assert len(lines) == 3


def test_rows_read_back_as_strings(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.tsv")
    ledger.append(row())
    (read,) = ledger.rows()
    assert set(read) == set(COLUMNS)
    assert read["exp_id"] == "exp-001"
    assert read["cents_total"] == "49.6"
    assert read["utc"].endswith("Z")


def test_spent_cents_sums_every_experiment(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.tsv")
    for cents in (49.6, 12, 0.4):
        ledger.append(row(cents_total=cents))
    assert ledger.spent_cents() == pytest.approx(62.0)
    assert Ledger(tmp_path / "ledger.tsv").spent_cents() == pytest.approx(62.0)


def test_a_description_with_tabs_newlines_and_quotes_stays_one_row(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.tsv")
    ledger.append(row(description='say "stop"\tthen\nwait'))
    ledger.append(row(exp_id="exp-002"))
    rows = ledger.rows()
    assert [r["exp_id"] for r in rows] == ["exp-001", "exp-002"]
    assert rows[0]["description"] == 'say "stop" then wait'


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (row(extra=1), "unknown ledger columns: extra"),
        ({k: v for k, v in row().items() if k != "verdict"}, "missing ledger columns: verdict"),
    ],
)
def test_append_rejects_the_wrong_columns(bad: dict, message: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=message):
        Ledger(tmp_path / "ledger.tsv").append(bad)


def test_append_rejects_cents_that_are_not_a_number(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.tsv")
    with pytest.raises(ValueError):
        ledger.append(row(cents_total="a lot"))
    assert ledger.rows() == []


def test_a_foreign_file_is_never_appended_to(tmp_path: Path) -> None:
    path = tmp_path / "ledger.tsv"
    path.write_text("something\telse\n", encoding="utf-8")
    ledger = Ledger(path)
    with pytest.raises(ValueError, match="unexpected header"):
        ledger.append(row())
    with pytest.raises(ValueError, match="unexpected header"):
        ledger.rows()
    assert path.read_text(encoding="utf-8") == "something\telse\n"
