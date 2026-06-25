"""Tests for name similarity.

Similarity drives the policy decisions: phone match + similar name -> auto;
phone match + different name -> review; near-identical names -> surface for review.
The score is order-independent and tolerant of typos.
"""

from matcher.normalize import name_similarity


class TestIdentity:
    def test_identical_is_one(self):
        assert name_similarity("Juan Perez", "Juan Perez") == 1.0

    def test_order_independent_is_one(self):
        assert name_similarity("ALONSO GUILLERMO", "Guillermo Alonso") == 1.0

    def test_accent_and_case_insensitive(self):
        assert name_similarity("José Pérez", "jose perez") == 1.0


class TestTypos:
    def test_single_typo_is_high(self):
        assert name_similarity("Juan Perez", "Juan Peres") > 0.8

    def test_extra_surname_is_moderately_high(self):
        assert name_similarity("Juan Perez", "Juan Perez Lopez") > 0.6


class TestDifferent:
    def test_different_people_is_low(self):
        assert name_similarity("Juan Perez", "Pedro Gomez") < 0.5


class TestUncomparable:
    def test_empty_against_name_is_zero(self):
        assert name_similarity("", "Juan Perez") == 0.0

    def test_none_against_name_is_zero(self):
        assert name_similarity(None, "Juan Perez") == 0.0
