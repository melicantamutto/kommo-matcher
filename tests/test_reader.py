"""Tests for reading xlsx/csv into a uniform Table.

The reader must survive the real-world quirks: duplicate header names (Kommo's
'Nombre' appears twice), empty columns, and choosing the column that actually
holds data (the phone lives in 'Teléfono oficina', not 'Teléfono celular').
"""

import csv

import openpyxl
import pytest

from matcher.reader import read_table


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "import.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PACIENTE", "TELEFONO", "DNI"])
        w.writerow(["ALONSO GUILLERMO", "", "40154219"])
        w.writerow(["GOMEZ LUCAS", "3515933958", ""])
    return path


@pytest.fixture
def xlsx_file(tmp_path):
    path = tmp_path / "contactos.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    # Duplicate 'Nombre' header, and an empty 'Teléfono celular' column.
    ws.append(["ID", "Nombre", "Nombre", "Teléfono celular", "Teléfono oficina"])
    ws.append([21742602, "Matias Anaya", "Matias", None, "'+5493515933958"])
    ws.append([21738546, "Pablo Simian", "Pablo", None, None])
    wb.save(path)
    return path


class TestReadCsv:
    def test_headers(self, csv_file):
        table = read_table(csv_file)
        assert table.headers == ["PACIENTE", "TELEFONO", "DNI"]

    def test_row_count(self, csv_file):
        assert len(read_table(csv_file).rows) == 2

    def test_value_by_column_name(self, csv_file):
        table = read_table(csv_file)
        assert table.values("DNI") == ["40154219", ""]


class TestReadXlsx:
    def test_headers_preserve_duplicates(self, xlsx_file):
        assert read_table(xlsx_file).headers == [
            "ID",
            "Nombre",
            "Nombre",
            "Teléfono celular",
            "Teléfono oficina",
        ]

    def test_duplicate_name_resolves_to_first_occurrence(self, xlsx_file):
        # The first 'Nombre' holds the full name; that is what we want.
        table = read_table(xlsx_file)
        assert table.values("Nombre") == ["Matias Anaya", "Pablo Simian"]

    def test_value_by_index(self, xlsx_file):
        table = read_table(xlsx_file)
        assert table.values(0) == ["21742602", "21738546"]

    def test_empty_cells_become_empty_string(self, xlsx_file):
        table = read_table(xlsx_file)
        assert table.values("Teléfono celular") == ["", ""]


class TestFillRateAndSuggest:
    def test_fill_rate_counts_non_empty(self, xlsx_file):
        table = read_table(xlsx_file)
        assert table.fill_rate("Teléfono oficina") == (1, 2)
        assert table.fill_rate("Teléfono celular") == (0, 2)

    def test_suggest_column_picks_most_filled(self, xlsx_file):
        table = read_table(xlsx_file)
        chosen = table.suggest_column(["Teléfono celular", "Teléfono oficina"])
        assert chosen == "Teléfono oficina"

    def test_suggest_column_ignores_absent_candidates(self, xlsx_file):
        table = read_table(xlsx_file)
        assert table.suggest_column(["No existe", "Teléfono oficina"]) == "Teléfono oficina"
