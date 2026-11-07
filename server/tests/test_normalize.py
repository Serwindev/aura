"""T-020a: Hindi normaliser — table-driven + property tests."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.extraction.normalize import (
    _HI_NUMBERS,
    contains_quote,
    extract_quantities,
    find_bp,
    numbers_in,
    temperature_c_candidates,
    weight_kg_candidates,
)

# every cardinal 0–99, every listed Devanagari spelling (≥100 cases on its own)
DEVANAGARI_CARDINALS = [
    (form, value)
    for value, forms in _HI_NUMBERS.items()
    for form in forms
    if any("ऀ" <= ch <= "ॿ" for ch in form)
]


@pytest.mark.parametrize(("word", "value"), DEVANAGARI_CARDINALS)
def test_every_devanagari_cardinal(word, value):
    assert numbers_in(word) == [value]


NUMBER_CASES = [
    ("एक सौ बीस", [120]),
    ("दो सौ", [200]),
    ("सौ", [100]),
    ("ek sau bees", [120]),
    ("do hazaar paanch sau", [2500]),
    ("एक हजार", [1000]),
    ("साढ़े तीन", [3.5]),
    ("साढ़े तीन सौ", [350]),
    ("साढ़े सात", [7.5]),
    ("सवा दो", [2.25]),
    ("पौने दो", [1.75]),
    ("डेढ़", [1.5]),
    ("ढाई किलो", [2.5]),
    ("नौ पॉइंट पांच", [9.5]),
    ("nau point paanch", [9.5]),
    ("do point aath", [2.8]),
    ("9 point 5", [9.5]),
    ("Hb नौ दशमलव दो", [9.2]),
    ("120", [120]),
    ("2.8", [2.8]),
    ("१२०", [120]),
    ("२.८", [2.8]),
    ("teen chaar din", [3, 4]),
    ("do teen", [2, 3]),
    ("one twenty", [120]),
    ("one forty five", [145]),
    ("twenty five", [25]),
    ("eighty", [80]),
    ("सातवें दिन", [7]),
    ("तीसरे दिन", [3]),
    ("चौदहवें दिन", [14]),
    ("बयालीसवें दिन", [42]),
    ("इक्कीसवें दिन", [21]),
    ("छठे महीने", [6]),
    ("day 7", [7]),
    ("7th day", [7]),
    ("बच्चा ठीक है", []),
    ("अड़तीस", [38]),
    ("अडतीस", [38]),  # nukta dropped
    ("पाँच", [5]),
    ("पांच", [5]),
    ("छः", [6]),
    ("100.4 F", [100.4]),
    ("तीन सौ पचास ग्राम", [350]),
    ("pulse ek sau das", [110]),
    ("saans saath", []),  # romanised "saath" (= with) is deliberately not 60
]


@pytest.mark.parametrize(("text", "expected"), NUMBER_CASES)
def test_numbers(text, expected):
    assert numbers_in(text) == pytest.approx(expected)


UNIT_CASES = [
    ("2.8 kg", 2.8, "kg"),
    ("दो किलो आठ सौ ग्राम", 2.8, "kg"),
    ("do kilo aath sau gram", 2.8, "kg"),
    ("2 kilo 800 gram", 2.8, "kg"),
    ("2 किलो और 500 ग्राम", 2.5, "kg"),
    ("2800 gram", 2800, "g"),
    ("सौ डिग्री", 100, "deg"),
    ("100 degree F", 100, "F"),
    ("38.5 C", 38.5, "C"),
    ("101 फारेनहाइट", 101, "F"),
    ("ढाई किलो", 2.5, "kg"),
]


@pytest.mark.parametrize(("text", "value", "unit"), UNIT_CASES)
def test_units(text, value, unit):
    qs = extract_quantities(text)
    assert len(qs) == 1
    assert qs[0].value == pytest.approx(value)
    assert qs[0].unit == unit


def test_span_points_at_original_text():
    text = "बच्चे का वजन दो किलो आठ सौ ग्राम है"
    (q,) = extract_quantities(text)
    assert q.text == "दो किलो आठ सौ ग्राम"
    assert text[q.start:q.end] == q.text


def test_span_with_nukta_is_not_shifted():
    text = "वज़न साढ़े तीन किलो"
    (q,) = extract_quantities(text)
    assert q.text == "साढ़े तीन किलो"


@pytest.mark.parametrize(("text", "expected"), [
    ("2800 gram", [2.8]),
    ("do kilo aath sau gram", [2.8]),
    ("वजन 3.1", [3.1]),
    ("वजन तीन किलो", [3.0]),
])
def test_weight_candidates(text, expected):
    assert weight_kg_candidates(text) == pytest.approx(expected)


@pytest.mark.parametrize(("text", "value", "converted"), [
    ("100 degree F", 37.8, True),
    ("sau degree bukhar", 37.8, True),
    ("तापमान सौ डिग्री", 37.8, True),
    ("38.5", 38.5, False),
    ("101.2 फारेनहाइट", 38.4, True),
    ("37 C", 37.0, False),
])
def test_temperature(text, value, converted):
    (c,) = temperature_c_candidates(text)
    assert c[0] == pytest.approx(value)
    assert c[1] is converted


@pytest.mark.parametrize(("text", "sys_", "dia"), [
    ("BP 120 by 80", 120, 80),
    ("BP 120/80", 120, 80),
    ("एक सौ बीस बटा अस्सी", 120, 80),
    ("bp one twenty by eighty", 120, 80),
    ("BP 110 over 70", 110, 70),
    ("140 बाई 90", 140, 90),
    ("बीपी एक सौ तीस बाय नब्बे", 130, 90),
])
def test_bp(text, sys_, dia):
    (bp,) = find_bp(text)
    assert (bp.systolic, bp.diastolic) == (sys_, dia)


def test_bp_absent():
    assert find_bp("वजन 3 किलो") == []


TRANSCRIPT = "बच्चे का वजन 2.8 किलो है। BP 120/80. Hb 9.5. बुखार नहीं है। दूध ठीक"


@pytest.mark.parametrize(("quote", "expected"), [
    ("वजन 2.8 किलो", True),
    ("वज़न 2.8 किलो", True),  # nukta variant
    ("वजन 2.9 किलो", False),
    ("जन 2.8", False),  # partial word
    ("", False),
    ("Hb 9.5", True),
    ("bp 120/80", True),
    ("120 / 80", True),
    ("बुखार नहीं है", True),
    ("बुखार है", False),
])
def test_contains_quote(quote, expected):
    assert contains_quote(TRANSCRIPT, quote) is expected


# ---- properties -----------------------------------------------------------

@given(st.integers(min_value=0, max_value=999_999))
def test_digit_strings_roundtrip(n):
    assert numbers_in(str(n)) == [n]


def _hindi(n: int) -> str:
    first = {v: forms[0] for v, forms in _HI_NUMBERS.items()}
    h, r = divmod(n, 100)
    parts = []
    if h:
        parts += [first[h], "सौ"]
    if r:
        parts.append(first[r])
    return " ".join(parts)


@given(st.integers(min_value=1, max_value=999))
def test_hindi_words_roundtrip(n):
    assert numbers_in(_hindi(n)) == [n]


@given(st.integers(min_value=0, max_value=99), st.integers(min_value=0, max_value=9))
def test_hindi_decimal_roundtrip(whole, tenth):
    first = {v: forms[0] for v, forms in _HI_NUMBERS.items()}
    text = f"{first[whole]} पॉइंट {first[tenth]}"
    assert numbers_in(text) == [pytest.approx(float(f"{whole}.{tenth}"))]
