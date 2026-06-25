"""Normalization of the fields used for identity matching.

Every value is reduced to a canonical, comparable form. When a value cannot be
normalized with confidence, the function returns None so the matcher treats it
as "no usable key" (sending the row to manual review instead of guessing).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

_NSN_LENGTH = 10
# Argentine area codes are 2 to 4 digits; the subscriber number fills the rest
# of the 10-digit national significant number.
_AREA_CODE_LENGTHS = (2, 3, 4)


def normalize_phone(raw: object) -> str | None:
    """Reduce an Argentine phone number to its 10-digit national significant number.

    The national significant number (NSN) is ``area_code + subscriber`` and is
    always 10 digits for Argentine mobiles. We strip the Excel apostrophe, the
    ``+``, the country code ``54``, the mobile ``9`` marker, the long-distance
    leading ``0`` and the local ``15`` prefix. If the value cannot be reduced to
    exactly 10 digits, we return None rather than risk a wrong match.
    """
    if raw is None:
        return None

    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return None

    # International dialing prefix.
    if digits.startswith("00"):
        digits = digits[2:]

    # Country code.
    if digits.startswith("54") and len(digits) > _NSN_LENGTH:
        digits = digits[2:]

    # Mobile marker: "9" sits between country code and area code (e.g. +54 9 ...).
    if digits.startswith("9") and len(digits) == _NSN_LENGTH + 1:
        digits = digits[1:]

    # Long-distance trunk prefix.
    if digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == _NSN_LENGTH:
        return digits

    # Local "15" mobile prefix: area_code + "15" + subscriber == 12 digits.
    if len(digits) == _NSN_LENGTH + 2:
        for area_len in _AREA_CODE_LENGTHS:
            if digits[area_len : area_len + 2] == "15":
                candidate = digits[:area_len] + digits[area_len + 2 :]
                if len(candidate) == _NSN_LENGTH:
                    return candidate

    return None


_MIN_DNI_DIGITS = 6


def normalize_dni(raw: object) -> str | None:
    """Reduce an Argentine DNI to its bare digits.

    Removes dots, spaces and any non-digit separators, then drops leading zeros
    so ``06402695`` and ``6402695`` compare equal. Returns None when the value is
    empty or has fewer than six digits (not a plausible DNI).
    """
    if raw is None:
        return None

    digits = re.sub(r"\D", "", str(raw)).lstrip("0")
    if len(digits) < _MIN_DNI_DIGITS:
        return None

    return digits


def normalize_name(raw: object) -> str | None:
    """Reduce a person name to an order-independent canonical form.

    Folds accents (including ``ñ`` -> ``n``), lowercases, drops punctuation and
    digits, then sorts the remaining word tokens so that "ALONSO GUILLERMO" and
    "Guillermo Alonso" produce the same value. Returns None when no word remains.
    """
    if raw is None:
        return None

    folded = unicodedata.normalize("NFKD", str(raw))
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = re.sub(r"[^a-zA-Z\s]", " ", folded).lower()

    tokens = folded.split()
    if not tokens:
        return None

    return " ".join(sorted(tokens))


_DATE_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",  # openpyxl datetime cell
    "%Y-%m-%d",  # ISO
    "%d.%m.%Y",  # Argentine dotted
    "%d/%m/%Y",  # Argentine slashed
    "%d-%m-%Y",
)


def normalize_date(raw: object) -> str | None:
    """Reduce a date to canonical ``YYYY-MM-DD``.

    Accepts Argentine day-first formats and ISO date/datetime strings. Returns
    None when the value is empty or cannot be parsed as a real calendar date.
    """
    if raw is None:
        return None

    text = str(raw).strip()
    if not text:
        return None

    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def name_similarity(a: object, b: object) -> float:
    """Return how similar two names are, from 0.0 to 1.0.

    Both names are reduced to their canonical form first, so the comparison is
    order-, accent- and case-insensitive. Returns 0.0 when either name is empty,
    so an unknown name never counts as a match.
    """
    canonical_a = normalize_name(a)
    canonical_b = normalize_name(b)
    if canonical_a is None or canonical_b is None:
        return 0.0
    if canonical_a == canonical_b:
        return 1.0

    return SequenceMatcher(None, canonical_a, canonical_b).ratio()
