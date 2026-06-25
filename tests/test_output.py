"""Tests for assembling the output table (original columns + matcher columns)."""

from matcher.models import Discrepancy, Outcome
from matcher.pipeline import OUTPUT_EXTRA, RowResult, row_estado, to_output_rows
from matcher.reader import Table


def import_table():
    return Table(headers=["PACIENTE", "DNI"], rows=[["ALONSO G", "40154219"], ["NUEVO", ""]])


class TestRowEstado:
    def test_no_match_is_nuevo(self):
        assert row_estado(RowResult(0, contacto_outcome=Outcome.NO_MATCH)) == "nuevo"

    def test_review_is_revisar_identidad(self):
        assert row_estado(RowResult(0, contacto_outcome=Outcome.REVIEW)) == "revisar_identidad"

    def test_clean_match_is_ok(self):
        assert row_estado(RowResult(0, id_contacto="C1", contacto_outcome=Outcome.AUTO_MATCH)) == "ok"

    def test_match_with_discrepancy_is_revisar_dato(self):
        result = RowResult(
            0,
            id_contacto="C1",
            contacto_outcome=Outcome.AUTO_MATCH,
            discrepancias=(Discrepancy("telefono", "111", "222"),),
        )
        assert row_estado(result) == "revisar_dato"


class TestToOutputRows:
    def test_preserves_original_columns_and_appends_extras(self):
        results = [
            RowResult(0, id_contacto="C1", contacto_outcome=Outcome.AUTO_MATCH, motivo_match="dni"),
            RowResult(1, contacto_outcome=Outcome.NO_MATCH),
        ]
        headers, rows = to_output_rows(import_table(), results)
        assert headers == ["PACIENTE", "DNI"] + OUTPUT_EXTRA
        assert rows[0][:2] == ["ALONSO G", "40154219"]
        assert rows[0][headers.index("id_contacto")] == "C1"
        assert rows[0][headers.index("estado")] == "ok"
        assert rows[1][headers.index("estado")] == "nuevo"
