"""Tests for name normalization.

The canonical form is order-independent, accent-insensitive and case-insensitive,
so "ALONSO GUILLERMO" (import: APELLIDO NOMBRE) matches "Guillermo Alonso"
(Kommo: nombre apellido). Tokens are sorted so word order never matters.
"""

import pytest

from matcher.normalize import normalize_name


class TestCanonicalForm:
    def test_uppercase_apellido_nombre(self):
        assert normalize_name("ALONSO GUILLERMO") == "alonso guillermo"

    def test_order_independent(self):
        assert normalize_name("Guillermo Alonso") == "alonso guillermo"

    def test_collapses_whitespace(self):
        assert normalize_name("  Guillermo   ALONSO ") == "alonso guillermo"

    def test_single_token(self):
        assert normalize_name("Gio") == "gio"


class TestAccentsAndPunctuation:
    def test_strips_accents(self):
        assert normalize_name("José María Pérez") == "jose maria perez"

    def test_enie_folded_to_n(self):
        assert normalize_name("Núñez José") == "jose nunez"

    def test_drops_punctuation(self):
        assert normalize_name("Pérez, Juan") == "juan perez"

    def test_drops_digits(self):
        assert normalize_name("Juan Perez 2") == "juan perez"


class TestEmpty:
    @pytest.mark.parametrize("value", [None, "", "   ", ",", "  -  ", "123"])
    def test_empty_returns_none(self, value):
        assert normalize_name(value) is None
