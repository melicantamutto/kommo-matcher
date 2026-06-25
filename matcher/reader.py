"""Read xlsx/csv files into a uniform Table the engine can consume.

This is the only place that touches file formats. It absorbs the real-world
quirks (duplicate header names, empty columns, mixed cell types) and exposes a
small, predictable API: headers, row values by name or index, fill rate, and a
helper that suggests which of several candidate columns actually holds data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import openpyxl


def _clean(value: object) -> str:
    """Turn any cell into a trimmed string; None and blanks become ''."""
    if value is None:
        return ""
    return str(value).strip()


@dataclass(frozen=True)
class Table:
    headers: list[str]
    rows: list[list[str]]

    def _index(self, column: int | str) -> int:
        if isinstance(column, int):
            return column
        # On duplicate header names, the first occurrence wins (Kommo's first
        # 'Nombre' holds the full name).
        return self.headers.index(column)

    def values(self, column: int | str) -> list[str]:
        idx = self._index(column)
        return [row[idx] if idx < len(row) else "" for row in self.rows]

    def fill_rate(self, column: int | str) -> tuple[int, int]:
        values = self.values(column)
        non_empty = sum(1 for v in values if v != "")
        return non_empty, len(values)

    def suggest_column(self, candidates: list[str]) -> str | None:
        """Return the candidate column with the most data, or None if none exist."""
        present = [c for c in candidates if c in self.headers]
        if not present:
            return None
        return max(present, key=lambda c: self.fill_rate(c)[0])


def read_table(path: str | Path) -> Table:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def _read_csv(path: Path) -> Table:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        all_rows = [[_clean(c) for c in row] for row in reader]
    if not all_rows:
        return Table(headers=[], rows=[])
    return Table(headers=all_rows[0], rows=all_rows[1:])


def _read_xlsx(path: Path) -> Table:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        return Table(headers=[], rows=[])
    headers = [_clean(h) for h in header]
    rows = [[_clean(c) for c in row] for row in rows_iter]
    wb.close()
    return Table(headers=headers, rows=rows)
