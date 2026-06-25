"""Tests for DNI normalization.

DNIs in the real data are 7-8 digit numbers (a few 6). openpyxl returns them as
ints, spreadsheets may carry dot separators, and leading zeros are pure
formatting. The canonical form is the bare digits with leading zeros removed.
"""

import pytest

from matcher.normalize import normalize_dni


class TestRealFormats:
    def test_plain_int_from_spreadsheet(self):
        assert normalize_dni(50741332) == "50741332"

    def test_eight_digit_string(self):
        assert normalize_dni("40154219") == "40154219"

    def test_dot_separators(self):
        assert normalize_dni("40.154.219") == "40154219"

    def test_surrounding_whitespace(self):
        assert normalize_dni("  24696101  ") == "24696101"


class TestLeadingZeros:
    """A 7-digit DNI written with a leading zero is the same number."""

    def test_leading_zero_stripped(self):
        assert normalize_dni("06402695") == "6402695"

    def test_seven_digit_with_dots(self):
        assert normalize_dni("6.402.695") == "6402695"

    def test_seven_digit_int(self):
        assert normalize_dni(6402695) == "6402695"


class TestUnusable:
    @pytest.mark.parametrize("value", [None, "", "   ", "abc", "no tiene", "-"])
    def test_empty_or_garbage_returns_none(self, value):
        assert normalize_dni(value) is None

    def test_too_short_returns_none(self):
        assert normalize_dni("1234") is None

    def test_only_zeros_returns_none(self):
        assert normalize_dni("000000") is None
