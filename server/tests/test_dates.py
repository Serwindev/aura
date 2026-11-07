"""Relative/explicit date resolution against the recording date. REF is a Tuesday."""

from datetime import date

import pytest

from app.extraction.dates_hi import add_months, resolve_date

REF = date(2026, 11, 10)


@pytest.mark.parametrize(("text", "direction", "expected"), [
    ("आज", "past", REF),
    ("aaj visit kiya", "past", REF),
    ("कल", "past", date(2026, 11, 9)),
    ("कल", "future", date(2026, 11, 11)),
    ("parso", "future", date(2026, 11, 12)),
    ("परसों", "past", date(2026, 11, 8)),
    ("tomorrow", "past", date(2026, 11, 11)),
    ("yesterday", "future", date(2026, 11, 9)),
    ("3 din baad", "future", date(2026, 11, 13)),
    ("तीन दिन बाद", "future", date(2026, 11, 13)),
    ("चार दिन बाद", "future", date(2026, 11, 14)),
    ("do din pehle", "future", date(2026, 11, 8)),
    ("ek hafte baad", "future", date(2026, 11, 17)),
    ("दो हफ्ते में", "future", date(2026, 11, 24)),
    ("agle hafte", "past", date(2026, 11, 17)),
    ("pichhle hafte", "future", date(2026, 11, 3)),
    ("अगले महीने", "future", date(2026, 12, 10)),
    ("ek mahine baad", "future", date(2026, 12, 10)),
    ("15 नवंबर", "future", date(2026, 11, 15)),
    ("15 नवंबर", "past", date(2025, 11, 15)),
    ("5 November", "past", date(2026, 11, 5)),
    ("pandrah November", "future", date(2026, 11, 15)),
    ("3 जनवरी 2027", "past", date(2027, 1, 3)),
    ("15 तारीख", "future", date(2026, 11, 15)),
    ("5 tarikh", "future", date(2026, 12, 5)),
    ("5 tarikh", "past", date(2026, 11, 5)),
    ("15 tarikh", "past", date(2026, 10, 15)),
    ("31 tarikh", "future", date(2026, 12, 31)),
    ("15/11/2026", "past", date(2026, 11, 15)),
    ("15-11-26", "past", date(2026, 11, 15)),
    ("2026-11-20", "past", date(2026, 11, 20)),
    ("somvar ko", "future", date(2026, 11, 16)),
    ("सोमवार", "past", date(2026, 11, 9)),
    ("agle somvar", "past", date(2026, 11, 16)),
    ("मंगलवार", "future", date(2026, 11, 17)),  # same weekday → next week
])
def test_resolve(text, direction, expected):
    assert resolve_date(text, REF, direction) == expected


@pytest.mark.parametrize("text", ["बच्चा ठीक है", "31/02/2026", "", "BP 120/80"])
def test_unresolvable(text):
    assert resolve_date(text, REF, "past") is None


def test_add_months_clamps():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert add_months(date(2026, 3, 15), -3) == date(2025, 12, 15)
