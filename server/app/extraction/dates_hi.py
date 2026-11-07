"""Resolve spoken Hindi/English date expressions against the recording date (deterministic).

"कल"/"kal" means both yesterday and tomorrow, so callers pass a direction:
- visit_date → "past"   (कल = yesterday)
- next_due   → "future" (कल = tomorrow)
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from typing import Literal

from .normalize import _parse_number, fold, tokenize

Direction = Literal["past", "future"]


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _f(words: str) -> set[str]:
    return {fold(w) for w in words.split()}


_TODAY = _f("आज aaj aj today")
_KAL = _f("कल kal")
_PARSO = _f("परसों परसो parso parson parsoon")
_TOMORROW = _f("tomorrow")
_YESTERDAY = _f("yesterday")
_AFTER = _f("बाद baad bad later after में mein me main")
_BEFORE = _f("पहले पहिले pehle pahle ago before")
_NEXT = _f("अगले अगला अगली agle agla agli next")
_LAST = _f("पिछले पिछला पिछली pichhle pichle pichhla last previous")
_TARIKH = _f("तारीख तारीक तरीख tarikh tareekh tarik date")

_UNIT_DAYS = {**{w: 1 for w in _f("दिन din day days")},
              **{w: 7 for w in _f("हफ्ते हफ्ता हफ़्ते हफ़्ता हफ्तों सप्ताह hafte hafta hafton saptah week weeks")}}
_UNIT_MONTHS = _f("महीने महीना महीनों mahine mahina mahino month months")

_MONTHS: dict[str, int] = {}
for _i, _names in enumerate([
    "जनवरी january jan", "फरवरी फ़रवरी february feb", "मार्च march mar",
    "अप्रैल अप्रेल april apr", "मई may", "जून june jun", "जुलाई july jul",
    "अगस्त august aug", "सितंबर सितम्बर september sep sept",
    "अक्टूबर अक्तूबर october oct", "नवंबर नवम्बर november nov",
    "दिसंबर दिसम्बर december dec"], start=1):
    for _n in _f(_names):
        _MONTHS[_n] = _i

_WEEKDAYS: dict[str, int] = {}
for _i, _names in enumerate([
    "सोमवार somvar monday", "मंगलवार mangalvar tuesday", "बुधवार budhvar wednesday",
    "गुरुवार बृहस्पतिवार guruvar brihaspativar thursday", "शुक्रवार shukravar friday",
    "शनिवार shanivar saturday", "रविवार इतवार ravivar itvar sunday"]):
    for _n in _f(_names):
        _WEEKDAYS[_n] = _i

_NUMERIC_DMY = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _shift(ref: date, n: int, unit: str, sign: int) -> date:
    if unit == "month":
        return add_months(ref, sign * n)
    return ref + timedelta(days=sign * n * _UNIT_DAYS[unit])


def _day_month(day: int, month: int, year: int | None, ref: date, direction: Direction) -> date | None:
    if year is not None:
        return _safe_date(year, month, day)
    cands = [c for c in (_safe_date(ref.year + k, month, day) for k in (-1, 0, 1)) if c]
    if direction == "future":
        fut = [c for c in cands if c >= ref]
        return min(fut) if fut else None
    past = [c for c in cands if c <= ref]
    return max(past) if past else None


def resolve_date(text: str, ref: date, direction: Direction) -> date | None:
    """Return the first date expressed in `text`, or None if nothing resolvable."""
    folded = fold(text)
    m = _ISO.search(folded)
    if m:
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    m = _NUMERIC_DMY.search(folded)
    if m:
        y = int(m[3])
        y = y + 2000 if y < 100 else y
        return _safe_date(y, int(m[2]), int(m[1]))

    toks = tokenize(text)
    norms = [t.norm for t in toks]
    sign = 1 if direction == "future" else -1
    i = 0
    while i < len(toks):
        n = norms[i]
        if n in _TODAY:
            return ref
        if n in _TOMORROW:
            return ref + timedelta(days=1)
        if n in _YESTERDAY:
            return ref - timedelta(days=1)
        if n in _KAL:
            return ref + timedelta(days=sign)
        if n in _PARSO:
            return ref + timedelta(days=2 * sign)
        if n in _NEXT or n in _LAST:
            s = 1 if n in _NEXT else -1
            if i + 1 < len(toks):
                u = norms[i + 1]
                if u in _UNIT_DAYS:
                    return ref + timedelta(days=s * _UNIT_DAYS[u])
                if u in _UNIT_MONTHS:
                    return add_months(ref, s)
                if u in _WEEKDAYS:
                    return _weekday(ref, _WEEKDAYS[u], "future" if s > 0 else "past")
        if n in _WEEKDAYS:
            return _weekday(ref, _WEEKDAYS[n], direction)

        parsed = _parse_number(toks, i) if toks[i].kind == "num" or _is_cardinal(n) else None
        if parsed is not None:
            value, j, _ = parsed
            num = int(value)
            if j < len(toks):
                u = norms[j]
                if u in _UNIT_DAYS or u in _UNIT_MONTHS:
                    unit = "month" if u in _UNIT_MONTHS else u
                    s = sign
                    rest = norms[j + 1: j + 4]
                    if any(w in _AFTER for w in rest):
                        s = 1
                    elif any(w in _BEFORE for w in rest):
                        s = -1
                    return _shift(ref, num, unit, s)
                if u in _MONTHS and 1 <= num <= 31:
                    year = None
                    if j + 1 < len(toks) and toks[j + 1].kind == "num" and len(toks[j + 1].norm) == 4:
                        year = int(toks[j + 1].norm)
                    return _day_month(num, _MONTHS[u], year, ref, direction)
                if u in _TARIKH and 1 <= num <= 31:
                    return _day_of_month(num, ref, direction)
            i = j
            continue
        i += 1
    return None


def _is_cardinal(norm: str) -> bool:
    from .normalize import _FRAC_WORDS_F, _MULT_F, _SMALL

    return norm in _SMALL or norm in _MULT_F or norm in _FRAC_WORDS_F


def _weekday(ref: date, wd: int, direction: Direction) -> date:
    if direction == "future":
        delta = (wd - ref.weekday()) % 7 or 7
        return ref + timedelta(days=delta)
    delta = (ref.weekday() - wd) % 7 or 7
    return ref - timedelta(days=delta)


def _day_of_month(day: int, ref: date, direction: Direction) -> date | None:
    this = _safe_date(ref.year, ref.month, day)
    if direction == "future":
        if this and this >= ref:
            return this
        nxt = add_months(date(ref.year, ref.month, 1), 1)
        return _safe_date(nxt.year, nxt.month, day)
    if this and this <= ref:
        return this
    prv = add_months(date(ref.year, ref.month, 1), -1)
    return _safe_date(prv.year, prv.month, day)
