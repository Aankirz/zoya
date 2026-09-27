"""The autotune ledger: one TSV row per experiment, and what the experiments have spent.

Standard library only; never imports zoya.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

COLUMNS = (
    "utc",
    "exp_id",
    "description",
    "patch_sha",
    "success_mean",
    "cents_total",
    "seconds_median",
    "verdict",
)


class Ledger:
    """A TSV with a header row of COLUMNS. Rows read back as dicts of strings."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, row: dict) -> None:
        """Add one experiment. `utc` defaults to now; every other column is required."""
        unknown = set(row) - set(COLUMNS)
        if unknown:
            raise ValueError(f"unknown ledger columns: {', '.join(sorted(unknown))}")
        row = {"utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), **row}
        missing = [column for column in COLUMNS if column not in row]
        if missing:
            raise ValueError(f"missing ledger columns: {', '.join(missing)}")
        float(row["cents_total"])  # spent_cents() must be able to add it up
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.path.exists() or self.path.stat().st_size == 0
        if not new:
            self._check_header()
        with self.path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, delimiter="\t", lineterminator="\n")
            if new:
                writer.writerow(COLUMNS)
            writer.writerow(_cell(row[column]) for column in COLUMNS)

    def rows(self) -> list[dict]:
        """Every experiment, oldest first."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            if reader.fieldnames is None:
                return []
            if tuple(reader.fieldnames) != COLUMNS:
                raise ValueError(f"{self.path}: unexpected header {reader.fieldnames}")
            return list(reader)

    def spent_cents(self) -> float:
        """The sum of `cents_total` over every experiment."""
        return sum(float(row["cents_total"] or 0) for row in self.rows())

    def _check_header(self) -> None:
        with self.path.open(encoding="utf-8", newline="") as file:
            header = next(csv.reader(file, delimiter="\t"), None)
        if header is None or tuple(header) != COLUMNS:
            raise ValueError(f"{self.path}: unexpected header {header}")


def _cell(value: object) -> str:
    """One TSV cell: tabs and line breaks become spaces so a row stays one line."""
    return " ".join(str(value).split()) if isinstance(value, str) else str(value)
