"""Domain model for the matching engine.

These are plain, immutable data carriers with no I/O and no UI. A KommoRecord is
one row of a Kommo export (contact or lead); an ImportRow is one row of the file
to be uploaded. Both carry pre-normalized keys plus the raw name for display and
similarity scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Outcome(str, Enum):
    """What the engine decided for an import row against one Kommo source."""

    AUTO_MATCH = "auto_match"  # confident: link automatically
    REVIEW = "review"  # human must decide
    NO_MATCH = "no_match"  # nothing found; leave the ID empty


class Reason(str, Enum):
    """Which signal produced the decision (for auditability)."""

    DNI = "dni"
    PHONE = "phone"
    NAME = "name"
    NONE = "none"


@dataclass(frozen=True)
class KommoRecord:
    """One row of a Kommo export. ``record_id`` is the ID we propagate."""

    record_id: str
    dni: str | None = None  # normalized
    phone: str | None = None  # normalized
    name: str | None = None  # canonical (sorted tokens)
    raw_name: str = ""  # original, for display and similarity
    birthdate: str | None = None  # normalized, for discrepancy detection


@dataclass(frozen=True)
class ImportRow:
    """One row of the database to be uploaded."""

    index: int  # position in the source file, for stable reference
    dni: str | None = None
    phone: str | None = None
    name: str | None = None
    raw_name: str = ""
    birthdate: str | None = None


@dataclass(frozen=True)
class Discrepancy:
    """A field that differs between the import row and the matched Kommo record.

    Identity is settled separately; this only flags a data value the user may want
    to reconcile. It never blocks linking.
    """

    field: str  # "nombre" | "telefono" | "fecha_nacimiento"
    kommo_value: str
    import_value: str


@dataclass(frozen=True)
class MatchResult:
    """The engine's verdict for one import row against one Kommo source."""

    outcome: Outcome
    reason: Reason
    matched_id: str | None = None
    candidate_ids: tuple[str, ...] = field(default_factory=tuple)
    review_cause: str | None = None  # human-readable why-review, when applicable
    discrepancies: tuple[Discrepancy, ...] = field(default_factory=tuple)
