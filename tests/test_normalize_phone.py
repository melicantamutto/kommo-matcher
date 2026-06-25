"""Tests for Argentine phone normalization.

The canonical form is the 10-digit national significant number (area + subscriber).
Cases are grounded in the real Kommo export data and in how Argentine mobile
numbering works (the 54 country code, the 9 mobile marker, the 0 trunk, the 15).
"""

import pytest

from matcher.normalize import normalize_phone


class TestKommoExportFormat:
    """Kommo stores phones as a text cell: leading apostrophe + +549 + 10 digits."""

    def test_strips_apostrophe_plus_country_and_mobile_marker(self):
        assert normalize_phone("'+5493537566234") == "3537566234"

    def test_cordoba_capital_number(self):
        assert normalize_phone("'+5493515933958") == "3515933958"

    def test_buenos_aires_number(self):
        assert normalize_phone("'+5491112345678") == "1112345678"


class TestInternationalFormats:
    def test_plus_with_spaces_and_dashes(self):
        assert normalize_phone("+54 9 351 593-3958") == "3515933958"

    def test_double_zero_international_prefix(self):
        assert normalize_phone("005493515933958") == "3515933958"


class TestLocalFormats:
    def test_already_national_significant_number(self):
        assert normalize_phone("3515933958") == "3515933958"

    def test_leading_zero_and_15_area_3_digits(self):
        # 0351 15 5933958  ->  351 + 5933958
        assert normalize_phone("0351 15 5933958") == "3515933958"

    def test_15_without_leading_zero_area_2_digits(self):
        # 11 15 12345678  ->  11 + 12345678
        assert normalize_phone("11 15 12345678") == "1112345678"

    def test_15_with_area_4_digits(self):
        # 3537 15 566234  ->  3537 + 566234
        assert normalize_phone("3537 15 566234") == "3537566234"


class TestUnnormalizable:
    """When in doubt, return None. Better no match than a wrong match."""

    @pytest.mark.parametrize("value", [None, "", "   ", "abc", "no aplica", "-"])
    def test_empty_or_garbage_returns_none(self, value):
        assert normalize_phone(value) is None

    def test_too_short_returns_none(self):
        assert normalize_phone("123456") is None

    def test_unrecognizable_length_returns_none(self):
        # 11 digits that are not a strippable 9-prefixed mobile
        assert normalize_phone("12345678901") is None
