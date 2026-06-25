"""Tests for the cascade matching engine — the agreed policy, case by case.

Policy (most to least confident):
  DNI matches                         -> AUTO_MATCH
  phone matches + name similar        -> AUTO_MATCH
  phone matches but name different    -> REVIEW   (mother/children share a phone)
  name only matches                   -> REVIEW   (a name alone never auto-confirms)
  a row matches 2+ records            -> REVIEW
  matched but data differs (name)     -> REVIEW   (same identity, divergent data)
  nothing matches                     -> NO_MATCH
"""

from matcher.matching import Matcher
from matcher.models import ImportRow, KommoRecord, Outcome, Reason
from matcher.normalize import normalize_date, normalize_dni, normalize_name, normalize_phone


def kommo(record_id, *, dni=None, phone=None, raw_name="", birthdate=None):
    return KommoRecord(
        record_id=record_id,
        dni=normalize_dni(dni),
        phone=normalize_phone(phone),
        name=normalize_name(raw_name),
        raw_name=raw_name,
        birthdate=normalize_date(birthdate),
    )


def row(*, dni=None, phone=None, raw_name="", birthdate=None):
    return ImportRow(
        index=0,
        dni=normalize_dni(dni),
        phone=normalize_phone(phone),
        name=normalize_name(raw_name),
        raw_name=raw_name,
        birthdate=normalize_date(birthdate),
    )


class TestDniTier:
    def test_dni_single_match_consistent_name_auto(self):
        m = Matcher([kommo("C1", dni="40154219", raw_name="ALONSO GUILLERMO")])
        result = m.match(row(dni="40.154.219", raw_name="Guillermo Alonso"))
        assert result.outcome is Outcome.AUTO_MATCH
        assert result.reason is Reason.DNI
        assert result.matched_id == "C1"

    def test_dni_match_links_even_when_name_differs_but_flags_it(self):
        # DNI is unique: identity is certain, so we link (fill the ID) and only
        # flag the differing name as a value to reconcile.
        m = Matcher([kommo("C1", dni="40154219", raw_name="ALONSO GUILLERMO")])
        result = m.match(row(dni="40154219", raw_name="ROBERTA SUAREZ"))
        assert result.outcome is Outcome.AUTO_MATCH
        assert result.reason is Reason.DNI
        assert result.matched_id == "C1"
        fields = {d.field for d in result.discrepancies}
        assert "nombre" in fields

    def test_dni_match_flags_phone_and_birthdate_discrepancies(self):
        m = Matcher(
            [kommo("C1", dni="40154219", phone="3515933958", raw_name="Juan Perez", birthdate="22.03.2001")]
        )
        result = m.match(
            row(dni="40154219", phone="3517778888", raw_name="Juan Perez", birthdate="23.03.2001")
        )
        assert result.outcome is Outcome.AUTO_MATCH
        assert result.matched_id == "C1"
        fields = {d.field for d in result.discrepancies}
        assert {"telefono", "fecha_nacimiento"} <= fields

    def test_dni_match_consistent_data_has_no_discrepancies(self):
        m = Matcher([kommo("C1", dni="40154219", raw_name="ALONSO GUILLERMO")])
        result = m.match(row(dni="40154219", raw_name="Guillermo Alonso"))
        assert result.outcome is Outcome.AUTO_MATCH
        assert result.discrepancies == ()

    def test_dni_matches_multiple_records_review(self):
        m = Matcher(
            [
                kommo("C1", dni="40154219", raw_name="ALONSO GUILLERMO"),
                kommo("C2", dni="40154219", raw_name="ALONSO GUILLERMO"),
            ]
        )
        result = m.match(row(dni="40154219", raw_name="ALONSO GUILLERMO"))
        assert result.outcome is Outcome.REVIEW
        assert set(result.candidate_ids) == {"C1", "C2"}


class TestPhoneTier:
    def test_phone_match_similar_name_auto(self):
        m = Matcher([kommo("C1", phone="'+5493515933958", raw_name="Juan Perez")])
        result = m.match(row(phone="3515933958", raw_name="Juan Peres"))
        assert result.outcome is Outcome.AUTO_MATCH
        assert result.reason is Reason.PHONE
        assert result.matched_id == "C1"

    def test_phone_match_different_name_review(self):
        # The real "mother and children share a phone" case.
        m = Matcher([kommo("C1", phone="3515933958", raw_name="Maria Gomez")])
        result = m.match(row(phone="3515933958", raw_name="Tomas Gomez"))
        assert result.outcome is Outcome.REVIEW
        assert result.reason is Reason.PHONE
        assert result.matched_id == "C1"

    def test_phone_match_without_name_is_conservative_review(self):
        m = Matcher([kommo("C1", phone="3515933958", raw_name="Maria Gomez")])
        result = m.match(row(phone="3515933958", raw_name=""))
        assert result.outcome is Outcome.REVIEW

    def test_phone_matches_multiple_review(self):
        m = Matcher(
            [
                kommo("C1", phone="3515933958", raw_name="Maria Gomez"),
                kommo("C2", phone="3515933958", raw_name="Maria Gomez"),
            ]
        )
        result = m.match(row(phone="3515933958", raw_name="Maria Gomez"))
        assert result.outcome is Outcome.REVIEW
        assert set(result.candidate_ids) == {"C1", "C2"}


class TestNameTier:
    def test_name_only_match_never_auto(self):
        m = Matcher([kommo("C1", raw_name="ALONSO GUILLERMO")])
        result = m.match(row(raw_name="Guillermo Alonso"))
        assert result.outcome is Outcome.REVIEW
        assert result.reason is Reason.NAME
        assert result.matched_id == "C1"


class TestCascadePriority:
    def test_dni_wins_even_when_phone_absent(self):
        m = Matcher(
            [
                kommo("C1", dni="40154219", raw_name="Juan Perez"),
                kommo("C2", phone="3515933958", raw_name="Juan Perez"),
            ]
        )
        result = m.match(row(dni="40154219", phone="3515933958", raw_name="Juan Perez"))
        assert result.matched_id == "C1"
        assert result.reason is Reason.DNI

    def test_falls_through_to_phone_when_dni_absent_in_kommo(self):
        m = Matcher([kommo("C2", phone="3515933958", raw_name="Juan Perez")])
        result = m.match(row(dni="40154219", phone="3515933958", raw_name="Juan Perez"))
        assert result.outcome is Outcome.AUTO_MATCH
        assert result.reason is Reason.PHONE
        assert result.matched_id == "C2"


class TestNoMatch:
    def test_nothing_matches(self):
        m = Matcher([kommo("C1", dni="40154219", phone="3515933958", raw_name="Juan Perez")])
        result = m.match(row(dni="11111111", phone="1112345678", raw_name="Otro Tipo"))
        assert result.outcome is Outcome.NO_MATCH
        assert result.reason is Reason.NONE
        assert result.matched_id is None
