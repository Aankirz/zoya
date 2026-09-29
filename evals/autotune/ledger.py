"""Autotune's TSV files: one row per task run, and what each night has spent.

Standard library only; never imports zoya.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

COLUMNS = ("utc", "night", "sha", "task", "group", "success", "cents", "seconds", "cause")


class Ledger:
    """A TSV with a header row of `columns`. Rows read back as dicts of strings."""

    def __init__(self, path: Path | str, columns: tuple[str, ...] = COLUMNS) -> None:
        self.path = Path(path)
        self.columns = columns

    def append(self, row: dict) -> None:
        """Add one row. `utc` defaults to now; every other column is required."""
        unknown = set(row) - set(self.columns)
        if unknown:
            raise ValueError(f"unknown ledger columns: {', '.join(sorted(unknown))}")
        row = {"utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), **row}
        missing = [column for column in self.columns if column not in row]
        if missing:
            raise ValueError(f"missing ledger columns: {', '.join(missing)}")
        if "cents" in self.columns:
            float(row["cents"])  # spent_cents() must be able to add it up
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.path.exists() or self.path.stat().st_size == 0
        if not new:
            self._check_header()
        with self.path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, delimiter="\t", lineterminator="\n")
            if new:
                writer.writerow(self.columns)
            writer.writerow(_cell(row[column]) for column in self.columns)

    def rows(self) -> list[dict]:
        """Every row, oldest first."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            if reader.fieldnames is None:
                return []
            if tuple(reader.fieldnames) != self.columns:
                raise ValueError(f"{self.path}: unexpected header {reader.fieldnames}")
            return list(reader)

    def spent_cents(self, night: str) -> float:
        """The sum of `cents` over the rows of one night."""
        return sum(float(row["cents"] or 0) for row in self.rows() if row["night"] == night)

    def _check_header(self) -> None:
        with self.path.open(encoding="utf-8", newline="") as file:
            header = next(csv.reader(file, delimiter="\t"), None)
        if header is None or tuple(header) != self.columns:
            raise ValueError(f"{self.path}: unexpected header {header}")


def _cell(value: object) -> str:
    """One TSV cell: tabs and line breaks become spaces so a row stays one line."""
    return " ".join(str(value).split()) if isinstance(value, str) else str(value)
