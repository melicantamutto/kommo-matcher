"""Tests for birth-date normalization.

Real data uses Argentine day-first formats (22.03.2001) and openpyxl renders date
cells as ISO datetimes (2001-03-22 00:00:00). The canonical form is YYYY-MM-DD so
two dates compare equal regardless of how they were written.
"""

import pytest

from matcher.normalize import normalize_date


class TestDayFirstFormats:
    def test_dotted(self):
        assert normalize_date("22.03.2001") == "2001-03-22"

    def test_slashed(self):
        assert normalize_date("22/03/2001") == "2001-03-22"

    def test_single_digit_day_month(self):
        assert normalize_date("7.9.1979") == "1979-09-07"


class TestIsoFormats:
    def test_iso_date(self):
        assert normalize_date("2001-03-22") == "2001-03-22"

    def test_iso_datetime_from_xlsx(self):
        assert normalize_date("2001-03-22 00:00:00") == "2001-03-22"


class TestUnusable:
    @pytest.mark.parametrize("value", [None, "", "   ", "no tiene", "32.13.2001", "abc"])
    def test_empty_or_invalid_returns_none(self, value):
        assert normalize_date(value) is None
