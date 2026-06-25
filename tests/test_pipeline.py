"""Tests for the end-to-end pipeline: tables + column mapping -> output rows.

This is the orchestration the app calls. It matches each import row against the
Kommo contacts (to get id_contacto, which links the new lead to an existing
contact) and against the Kommo leads (to flag a duplicate lead), and produces an
auditable output row per input row.
"""

from matcher.models import Outcome
from matcher.pipeline import ColumnMap, build_import_rows, build_kommo_records, run_matching
from matcher.reader import Table


def contacts_table():
    return Table(
        headers=["ID", "Nombre", "DNI", "Tel"],
        rows=[
            ["C1", "Guillermo Alonso", "40154219", "3515933958"],
            ["C2", "Maria Gomez", "", "3514444444"],
        ],
    )


def leads_table():
    return Table(
        headers=["ID", "Nombre", "DNI", "Tel"],
        rows=[["L1", "Guillermo Alonso", "40154219", ""]],
    )


def import_table():
    return Table(
        headers=["PACIENTE", "DNI", "TELEFONO"],
        rows=[
            ["ALONSO GUILLERMO", "40.154.219", ""],  # exists as contact AND lead
            ["GOMEZ MARIA", "", "3514444444"],  # contact only
            ["NUEVO TIPO", "99888777", "1112223333"],  # brand new
        ],
    )


class TestBuilders:
    def test_build_kommo_records_normalizes_and_keeps_id(self):
        records = build_kommo_records(
            contacts_table(), ColumnMap(id="ID", dni="DNI", phone="Tel", name="Nombre")
        )
        assert records[0].record_id == "C1"
        assert records[0].dni == "40154219"
        assert records[0].phone == "3515933958"
        assert records[0].name == "alonso guillermo"

    def test_build_import_rows_carries_index(self):
        rows = build_import_rows(
            import_table(), ColumnMap(dni="DNI", phone="TELEFONO", name="PACIENTE")
        )
        assert rows[0].index == 0
        assert rows[0].dni == "40154219"
        assert rows[1].phone == "3514444444"


class TestRunMatching:
    def setup_method(self):
        self.contacts = build_kommo_records(
            contacts_table(), ColumnMap(id="ID", dni="DNI", phone="Tel", name="Nombre")
        )
        self.leads = build_kommo_records(
            leads_table(), ColumnMap(id="ID", dni="DNI", phone="Tel", name="Nombre")
        )
        self.results = run_matching(
            import_table(),
            ColumnMap(dni="DNI", phone="TELEFONO", name="PACIENTE"),
            self.contacts,
            self.leads,
        )

    def test_one_result_per_import_row(self):
        assert len(self.results) == 3

    def test_contact_match_fills_id_contacto(self):
        assert self.results[0].id_contacto == "C1"
        assert self.results[0].contacto_outcome is Outcome.AUTO_MATCH
        assert self.results[0].motivo_match == "dni"

    def test_existing_lead_is_flagged(self):
        assert self.results[0].id_lead == "L1"
        assert self.results[0].ya_existe_como_lead is True

    def test_contact_only_has_no_lead(self):
        assert self.results[1].id_contacto == "C2"
        assert self.results[1].id_lead == ""
        assert self.results[1].ya_existe_como_lead is False

    def test_brand_new_row_leaves_ids_empty(self):
        assert self.results[2].id_contacto == ""
        assert self.results[2].id_lead == ""
        assert self.results[2].contacto_outcome is Outcome.NO_MATCH
