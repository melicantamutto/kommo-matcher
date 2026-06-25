"""End-to-end orchestration: tables + column mapping -> auditable output rows.

The app is a thin shell over this module. Given the import table and the two
Kommo sources, it matches each row against the contacts (to obtain id_contacto,
which links a new lead to an existing contact) and against the leads (to flag a
duplicate lead), and returns one result per input row.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from matcher.matching import Matcher
from matcher.models import Discrepancy, ImportRow, KommoRecord, Outcome, Reason
from matcher.normalize import normalize_date, normalize_dni, normalize_name, normalize_phone
from matcher.reader import Table


@dataclass(frozen=True)
class ColumnMap:
    """Which column holds each field. None means the field is absent."""

    dni: int | str | None = None
    phone: int | str | None = None
    name: int | str | None = None
    birthdate: int | str | None = None
    id: int | str | None = None  # only for Kommo sources


def _pick(table: Table, column: int | str | None) -> list[str]:
    if column is None:
        return [""] * len(table.rows)
    return table.values(column)


def build_kommo_records(table: Table, mapping: ColumnMap) -> list[KommoRecord]:
    ids = _pick(table, mapping.id)
    dnis = _pick(table, mapping.dni)
    phones = _pick(table, mapping.phone)
    names = _pick(table, mapping.name)
    births = _pick(table, mapping.birthdate)
    return [
        KommoRecord(
            record_id=ids[i],
            dni=normalize_dni(dnis[i]),
            phone=normalize_phone(phones[i]),
            name=normalize_name(names[i]),
            raw_name=names[i],
            birthdate=normalize_date(births[i]),
        )
        for i in range(len(table.rows))
    ]


def build_import_rows(table: Table, mapping: ColumnMap) -> list[ImportRow]:
    dnis = _pick(table, mapping.dni)
    phones = _pick(table, mapping.phone)
    names = _pick(table, mapping.name)
    births = _pick(table, mapping.birthdate)
    return [
        ImportRow(
            index=i,
            dni=normalize_dni(dnis[i]),
            phone=normalize_phone(phones[i]),
            name=normalize_name(names[i]),
            raw_name=names[i],
            birthdate=normalize_date(births[i]),
        )
        for i in range(len(table.rows))
    ]


@dataclass
class RowResult:
    """One import row's verdict against both Kommo sources, ready for output."""

    row_index: int
    id_contacto: str = ""
    contacto_outcome: Outcome = Outcome.NO_MATCH
    motivo_match: str = ""
    contacto_candidatos: tuple[str, ...] = field(default_factory=tuple)
    contacto_review_cause: str | None = None
    discrepancias: tuple[Discrepancy, ...] = field(default_factory=tuple)
    id_lead: str = ""
    ya_existe_como_lead: bool = False
    lead_outcome: Outcome = Outcome.NO_MATCH
    lead_candidatos: tuple[str, ...] = field(default_factory=tuple)


def row_estado(result: RowResult) -> str:
    """A single human-facing status combining identity and data reconciliation."""
    if result.contacto_outcome is Outcome.NO_MATCH:
        return "nuevo"
    if result.contacto_outcome is Outcome.REVIEW:
        return "revisar_identidad"
    if result.discrepancias:
        return "revisar_dato"
    return "ok"


OUTPUT_EXTRA = [
    "id_contacto",
    "id_lead",
    "ya_existe_como_lead",
    "motivo_match",
    "estado",
    "candidatos",
    "discrepancias",
    "detalle_revision",
]


def _format_discrepancies(result: RowResult) -> str:
    return "; ".join(
        f"{d.field}: kommo='{d.kommo_value}' nuevo='{d.import_value}'"
        for d in result.discrepancias
    )


def to_output_rows(
    import_table: Table, results: list[RowResult]
) -> tuple[list[str], list[list[str]]]:
    """Build the output table: every original column plus the matcher's columns."""
    headers = list(import_table.headers) + OUTPUT_EXTRA
    rows: list[list[str]] = []
    for result, source in zip(results, import_table.rows):
        candidatos = (
            "|".join(result.contacto_candidatos)
            if result.contacto_outcome is Outcome.REVIEW
            else ""
        )
        rows.append(
            list(source)
            + [
                result.id_contacto,
                result.id_lead,
                "si" if result.ya_existe_como_lead else "",
                result.motivo_match,
                row_estado(result),
                candidatos,
                _format_discrepancies(result),
                result.contacto_review_cause or "",
            ]
        )
    return headers, rows


def run_matching(
    import_table: Table,
    import_map: ColumnMap,
    contacts: list[KommoRecord],
    leads: list[KommoRecord],
) -> list[RowResult]:
    contact_matcher = Matcher(contacts)
    lead_matcher = Matcher(leads)
    rows = build_import_rows(import_table, import_map)

    results: list[RowResult] = []
    for row in rows:
        contact = contact_matcher.match(row)
        lead = lead_matcher.match(row)

        result = RowResult(row_index=row.index)
        # An ID is auto-filled only on a confident match; review/no-match leave it
        # empty so the importer creates the record (or the user decides first).
        if contact.outcome is Outcome.AUTO_MATCH and contact.matched_id:
            result.id_contacto = contact.matched_id
        result.contacto_outcome = contact.outcome
        result.motivo_match = contact.reason.value if contact.reason is not Reason.NONE else ""
        result.contacto_candidatos = contact.candidate_ids or (
            (contact.matched_id,) if contact.matched_id else ()
        )
        result.contacto_review_cause = contact.review_cause
        result.discrepancias = contact.discrepancies

        if lead.outcome is Outcome.AUTO_MATCH and lead.matched_id:
            result.id_lead = lead.matched_id
            result.ya_existe_como_lead = True
        result.lead_outcome = lead.outcome
        result.lead_candidatos = lead.candidate_ids or (
            (lead.matched_id,) if lead.matched_id else ()
        )

        results.append(result)

    return results
