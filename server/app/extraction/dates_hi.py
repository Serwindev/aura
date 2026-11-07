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
    for d, _, _ in iter_date_phrases(text, ref, direction):
        return d
    return None


_DIG = "0-9०-९"
_NUMERIC_DMY_RAW = re.compile(rf"(?<![{_DIG}])([{_DIG}]{{1,2}})[/.-]([{_DIG}]{{1,2}})[/.-]([{_DIG}]{{2,4}})(?![{_DIG}])")
_ISO_RAW = re.compile(rf"(?<![{_DIG}])([{_DIG}]{{4}})-([{_DIG}]{{2}})-([{_DIG}]{{2}})(?![{_DIG}])")


def _int(s: str) -> int:
    return int(fold(s))


def iter_date_phrases(text: str, ref: date, direction: Direction):
    """Yield (date, start, end) for every resolvable date phrase, in text order.
    Spans are offsets into the original text. A bare "N din" needs a direction word
    (बाद/पहले/में...) — "3 दिन का बच्चा" is an age, not a date."""
    found: list[tuple[date, int, int]] = []
    taken: list[tuple[int, int]] = []
    for m in _ISO_RAW.finditer(text):
        d = _safe_date(_int(m[1]), _int(m[2]), _int(m[3]))
        taken.append((m.start(), m.end()))
        if d:
            found.append((d, m.start(), m.end()))
    for m in _NUMERIC_DMY_RAW.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        y = _int(m[3])
        y = y + 2000 if y < 100 else y
        d = _safe_date(y, _int(m[2]), _int(m[1]))
        taken.append((m.start(), m.end()))
        if d:
            found.append((d, m.start(), m.end()))

    toks = [t for t in tokenize(text) if not any(a <= t.start < b for a, b in taken)]
    norms = [t.norm for t in toks]
    sign = 1 if direction == "future" else -1

    def add(d: date | None, i: int, j: int) -> None:
        if d is not None:
            found.append((d, toks[i].start, toks[j - 1].end))

    i = 0
    while i < len(toks):
        n = norms[i]
        if n in _TODAY:
            add(ref, i, i + 1)
        elif n in _TOMORROW:
            add(ref + timedelta(days=1), i, i + 1)
        elif n in _YESTERDAY:
            add(ref - timedelta(days=1), i, i + 1)
        elif n in _KAL:
            add(ref + timedelta(days=sign), i, i + 1)
        elif n in _PARSO:
            add(ref + timedelta(days=2 * sign), i, i + 1)
        elif (n in _NEXT or n in _LAST) and i + 1 < len(toks) and (
                norms[i + 1] in _UNIT_DAYS or norms[i + 1] in _UNIT_MONTHS or norms[i + 1] in _WEEKDAYS):
            s = 1 if n in _NEXT else -1
            u = norms[i + 1]
            if u in _UNIT_DAYS:
                add(ref + timedelta(days=s * _UNIT_DAYS[u]), i, i + 2)
            elif u in _UNIT_MONTHS:
                add(add_months(ref, s), i, i + 2)
            else:
                add(_weekday(ref, _WEEKDAYS[u], "future" if s > 0 else "past"), i, i + 2)
            i += 2
            continue
        elif n in _WEEKDAYS:
            add(_weekday(ref, _WEEKDAYS[n], direction), i, i + 1)
        else:
            parsed = _parse_number(toks, i) if toks[i].kind == "num" or _is_cardinal(n) else None
            if parsed is not None:
                value, j, _ = parsed
                num = int(value)
                if j < len(toks):
                    u = norms[j]
                    if u in _UNIT_DAYS or u in _UNIT_MONTHS:
                        unit = "month" if u in _UNIT_MONTHS else u
                        rest = norms[j + 1: j + 4]
                        k = next((x for x, w in enumerate(rest) if w in _AFTER or w in _BEFORE), None)
                        if k is not None:
                            s = 1 if rest[k] in _AFTER else -1
                            add(_shift(ref, num, unit, s), i, j + 2 + k)
                            i = j + 2 + k
                            continue
                    elif u in _MONTHS and 1 <= num <= 31:
                        year, end = None, j + 1
                        if j + 1 < len(toks) and toks[j + 1].kind == "num" and len(toks[j + 1].norm) == 4:
                            year, end = int(toks[j + 1].norm), j + 2
                        add(_day_month(num, _MONTHS[u], year, ref, direction), i, end)
                        i = end
                        continue
                    elif u in _TARIKH and 1 <= num <= 31:
                        add(_day_of_month(num, ref, direction), i, j + 1)
                        i = j + 1
                        continue
                i = max(j, i + 1)
                continue
        i += 1
    found.sort(key=lambda x: x[1])
    yield from found


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
