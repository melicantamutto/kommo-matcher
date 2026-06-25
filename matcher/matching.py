"""The cascade matching engine.

Given a set of Kommo records, decide for each import row whether it matches an
existing record, and with how much confidence. The cascade goes from the
strongest signal (DNI) to the weakest (name), and applies the agreed policy:
a name alone never auto-confirms, and any data discrepancy on a match is sent to
human review. When in doubt the engine prefers REVIEW over a wrong link.
"""

from __future__ import annotations

from collections import defaultdict

from matcher.models import Discrepancy, ImportRow, KommoRecord, MatchResult, Outcome, Reason
from matcher.normalize import name_similarity, normalize_name

# Below this name similarity, two names are considered "different" and the match
# is sent to review instead of being auto-confirmed.
DEFAULT_NAME_THRESHOLD = 0.85


class Matcher:
    def __init__(
        self,
        records: list[KommoRecord],
        name_threshold: float = DEFAULT_NAME_THRESHOLD,
    ) -> None:
        self.name_threshold = name_threshold
        self._by_dni: dict[str, list[KommoRecord]] = defaultdict(list)
        self._by_phone: dict[str, list[KommoRecord]] = defaultdict(list)
        self._by_name: dict[str, list[KommoRecord]] = defaultdict(list)
        for record in records:
            if record.dni:
                self._by_dni[record.dni].append(record)
            if record.phone:
                self._by_phone[record.phone].append(record)
            if record.name:
                self._by_name[record.name].append(record)

    def match(self, row: ImportRow) -> MatchResult:
        return (
            self._match_by_dni(row)
            or self._match_by_phone(row)
            or self._match_by_name(row)
            or MatchResult(outcome=Outcome.NO_MATCH, reason=Reason.NONE)
        )

    def _match_by_dni(self, row: ImportRow) -> MatchResult | None:
        if not row.dni:
            return None
        hits = self._by_dni.get(row.dni)
        if not hits:
            return None
        if len(hits) > 1:
            return self._ambiguous(hits, Reason.DNI, "Same DNI on several Kommo records")

        record = hits[0]
        # DNI is unique: identity is certain. We always link and only flag any
        # differing data values for the user to reconcile.
        return MatchResult(
            outcome=Outcome.AUTO_MATCH,
            reason=Reason.DNI,
            matched_id=record.record_id,
            discrepancies=self._discrepancies(row, record),
        )

    def _match_by_phone(self, row: ImportRow) -> MatchResult | None:
        if not row.phone:
            return None
        hits = self._by_phone.get(row.phone)
        if not hits:
            return None
        if len(hits) > 1:
            return self._ambiguous(hits, Reason.PHONE, "Same phone on several Kommo records")

        record = hits[0]
        # A phone is shared (mother/children), so identity is only certain when the
        # name also agrees. If it differs, a human decides whether to link at all.
        if self._name_differs(row, record):
            return MatchResult(
                outcome=Outcome.REVIEW,
                reason=Reason.PHONE,
                matched_id=record.record_id,
                candidate_ids=(record.record_id,),
                review_cause="Phone matches but the name differs or is missing",
                discrepancies=self._discrepancies(row, record),
            )
        return MatchResult(
            outcome=Outcome.AUTO_MATCH,
            reason=Reason.PHONE,
            matched_id=record.record_id,
            discrepancies=self._discrepancies(row, record),
        )

    def _match_by_name(self, row: ImportRow) -> MatchResult | None:
        if not row.name:
            return None
        hits = self._by_name.get(row.name)
        if not hits:
            return None
        # A name alone never auto-confirms.
        if len(hits) > 1:
            return self._ambiguous(hits, Reason.NAME, "Same name on several Kommo records")
        record = hits[0]
        return MatchResult(
            outcome=Outcome.REVIEW,
            reason=Reason.NAME,
            matched_id=record.record_id,
            candidate_ids=(record.record_id,),
            review_cause="Only the name matches; confirm it is the same person",
        )

    def _name_differs(self, row: ImportRow, record: KommoRecord) -> bool:
        return name_similarity(row.raw_name, record.raw_name) < self.name_threshold

    def _discrepancies(self, row: ImportRow, record: KommoRecord) -> tuple[Discrepancy, ...]:
        """Flag fields present on both sides whose values differ.

        These never block linking; they are values the user may want to reconcile
        in the output so the imported lead carries the correct data.
        """
        found: list[Discrepancy] = []
        if row.name and record.name and normalize_name(row.raw_name) != normalize_name(record.raw_name):
            found.append(Discrepancy("nombre", record.raw_name, row.raw_name))
        if row.phone and record.phone and row.phone != record.phone:
            found.append(Discrepancy("telefono", record.phone, row.phone))
        if row.birthdate and record.birthdate and row.birthdate != record.birthdate:
            found.append(Discrepancy("fecha_nacimiento", record.birthdate, row.birthdate))
        return tuple(found)

    def _ambiguous(self, hits: list[KommoRecord], reason: Reason, cause: str) -> MatchResult:
        return MatchResult(
            outcome=Outcome.REVIEW,
            reason=reason,
            candidate_ids=tuple(r.record_id for r in hits),
            review_cause=cause,
        )
