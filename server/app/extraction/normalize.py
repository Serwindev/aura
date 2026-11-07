"""Hindi / Hinglish normaliser (T-020a).

Turns spoken numbers ("एक सौ बीस", "do kilo aath sau gram", "Hb nau point paanch",
"BP 120 by 80") into values *with the span of the original text they came from*.

Design rules:
- Deterministic code only. The LLM supplies an evidence quote; this module derives
  the number from that quote so the LLM never "owns" a clinical value.
- Spans are offsets into the ORIGINAL string (no lossy re-indexing).
- Ambiguous romanised words are deliberately left out of the lexicon (e.g. "saath"
  = 60 or "with"; "no" = 9 or English "no"). Devanagari forms are unambiguous.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Text folding
# ---------------------------------------------------------------------------

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUKTA = "़"
_CHANDRABINDU = "ँ"
_ANUSVARA = "ं"


def fold(text: str) -> str:
    """Canonical form for comparison: NFC, ASCII digits, no nukta, ँ→ं, lowercase."""
    t = unicodedata.normalize("NFC", text)
    t = unicodedata.normalize("NFD", t)  # split precomposed nukta letters (e.g. ड़ U+095C)
    t = t.replace(_NUKTA, "").replace(_CHANDRABINDU, _ANUSVARA)
    t = unicodedata.normalize("NFC", t)
    return t.translate(_DEV_DIGITS).lower()


# a '.' survives only as a decimal point (digit on both sides); dandas, commas etc. go
_PUNCT_RE = re.compile(r"[.](?!\d)|(?<!\d)[.]|[^\w\sऀ-ॣ०-ॿ./]|_")
_SPACE_RE = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    """Fold + strip punctuation (keeping decimal points and '/') + collapse spaces."""
    t = fold(text)
    t = _PUNCT_RE.sub(" ", t).replace("/", " / ")
    return _SPACE_RE.sub(" ", t).strip()


def contains_quote(transcript: str, quote: str) -> bool:
    """True if the (normalised) quote occurs in the (normalised) transcript on word boundaries."""
    q = normalize_for_match(quote)
    if not q:
        return False
    t = f" {normalize_for_match(transcript)} "
    return f" {q} " in t


# ---------------------------------------------------------------------------
# Lexicon
# ---------------------------------------------------------------------------

# value -> variants (Devanagari first, then common romanisations)
_HI_NUMBERS: dict[int, list[str]] = {
    0: ["शून्य", "ज़ीरो", "जीरो", "shunya", "zero"],
    1: ["एक", "ek"],
    2: ["दो", "do"],
    3: ["तीन", "teen", "tin"],
    4: ["चार", "char", "chaar"],
    5: ["पांच", "पाँच", "पाच", "paanch", "panch", "paach"],
    6: ["छह", "छः", "छे", "छै", "chhah", "chhe", "chhah", "chah", "che"],
    7: ["सात", "saat", "sat"],
    8: ["आठ", "aath", "ath"],
    9: ["नौ", "nau"],
    10: ["दस", "das", "dus"],
    11: ["ग्यारह", "gyarah", "gyara", "gyaarah"],
    12: ["बारह", "barah", "bara", "baarah"],
    13: ["तेरह", "terah", "tera"],
    14: ["चौदह", "chaudah", "chauda"],
    15: ["पंद्रह", "पन्द्रह", "pandrah", "pandra"],
    16: ["सोलह", "solah", "sola"],
    17: ["सत्रह", "satrah", "satra"],
    18: ["अठारह", "atharah", "athara", "athaarah"],
    19: ["उन्नीस", "unnis", "unnees"],
    20: ["बीस", "bees", "bis"],
    21: ["इक्कीस", "ikkees", "ikkis"],
    22: ["बाईस", "baees", "bais", "baais"],
    23: ["तेईस", "teis", "teees", "teyis"],
    24: ["चौबीस", "chaubees", "chaubis"],
    25: ["पच्चीस", "pachchees", "pachees", "pachis", "pacchis"],
    26: ["छब्बीस", "chhabbees", "chabbis"],
    27: ["सत्ताईस", "sattaees", "sattais"],
    28: ["अट्ठाईस", "अठाईस", "atthaees", "athais", "atthais"],
    29: ["उनतीस", "untees", "untis"],
    30: ["तीस", "tees", "tis"],
    31: ["इकतीस", "iktees", "iktis"],
    32: ["बत्तीस", "battees", "battis"],
    33: ["तैंतीस", "taintees", "taintis"],
    34: ["चौंतीस", "chauntees", "chauntis"],
    35: ["पैंतीस", "paintees", "paintis"],
    36: ["छत्तीस", "chhattees", "chattis"],
    37: ["सैंतीस", "saintees", "saintis"],
    38: ["अड़तीस", "adtees", "adtis"],
    39: ["उनतालीस", "untaalees", "untalis"],
    40: ["चालीस", "chaalees", "chalis"],
    41: ["इकतालीस", "iktaalees", "iktalis"],
    42: ["बयालीस", "bayaalees", "bayalis"],
    43: ["तैंतालीस", "taintaalees", "taintalis"],
    44: ["चवालीस", "चौवालीस", "chavaalees", "chavalis"],
    45: ["पैंतालीस", "paintaalees", "paintalis"],
    46: ["छियालीस", "chhiyaalees", "chhiyalis"],
    47: ["सैंतालीस", "saintaalees", "saintalis"],
    48: ["अड़तालीस", "adtaalees", "adtalis"],
    49: ["उनचास", "unchaas", "unchas"],
    50: ["पचास", "pachaas", "pachas"],
    51: ["इक्यावन", "ikyaavan", "ikyavan"],
    52: ["बावन", "baavan", "bavan"],
    53: ["तिरेपन", "tirepan"],
    54: ["चौवन", "chauvan"],
    55: ["पचपन", "pachpan"],
    56: ["छप्पन", "chhappan"],
    57: ["सत्तावन", "sattaavan", "sattavan"],
    58: ["अट्ठावन", "atthaavan", "atthavan"],
    59: ["उनसठ", "unsath"],
    60: ["साठ"],  # romanised "saath" omitted: also means "with"
    61: ["इकसठ", "iksath"],
    62: ["बासठ", "baasath"],
    63: ["तिरेसठ", "tiresath"],
    64: ["चौंसठ", "chaunsath"],
    65: ["पैंसठ", "painsath"],
    66: ["छियासठ", "chhiyaasath"],
    67: ["सड़सठ", "sadsath"],
    68: ["अड़सठ", "adsath"],
    69: ["उनहत्तर", "unhattar"],
    70: ["सत्तर", "sattar"],
    71: ["इकहत्तर", "ikhattar"],
    72: ["बहत्तर", "bahattar"],
    73: ["तिहत्तर", "tihattar"],
    74: ["चौहत्तर", "chauhattar"],
    75: ["पचहत्तर", "pachhattar", "pachattar"],
    76: ["छिहत्तर", "chhihattar"],
    77: ["सतहत्तर", "sathattar"],
    78: ["अठहत्तर", "athhattar"],
    79: ["उन्यासी", "unyaasi"],
    80: ["अस्सी", "assi"],
    81: ["इक्यासी", "ikyaasi"],
    82: ["बयासी", "bayaasi"],
    83: ["तिरासी", "tiraasi"],
    84: ["चौरासी", "chauraasi"],
    85: ["पचासी", "pachaasi"],
    86: ["छियासी", "chhiyaasi"],
    87: ["सत्तासी", "sattaasi"],
    88: ["अट्ठासी", "atthaasi"],
    89: ["नवासी", "navaasi"],
    90: ["नब्बे", "nabbe"],
    91: ["इक्यानबे", "ikyaanbe"],
    92: ["बानबे", "baanbe"],
    93: ["तिरानबे", "tiraanbe"],
    94: ["चौरानबे", "chauraanbe"],
    95: ["पचानबे", "pachaanbe"],
    96: ["छियानबे", "chhiyaanbe"],
    97: ["सत्तानबे", "sattaanbe"],
    98: ["अट्ठानबे", "atthaanbe"],
    99: ["निन्यानबे", "ninyaanbe"],
}

_EN_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_EN_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}

_MULTIPLIERS = {"सौ": 100, "sau": 100, "hundred": 100,
                "हज़ार": 1000, "हजार": 1000, "hazar": 1000, "hazaar": 1000, "thousand": 1000}

_POINT = {"point", "पॉइंट", "पोइंट", "प्वाइंट", "पाइंट", "दशमलव", "dashamlav", "dashmalav"}

# prefix modifiers applied to the following number: साढ़े तीन = 3.5, सवा दो = 2.25, पौने दो = 1.75
_FRAC_PREFIX = {"साढ़े": 0.5, "साढे": 0.5, "saadhe": 0.5, "sadhe": 0.5, "saade": 0.5, "sade": 0.5,
                "सवा": 0.25, "sava": 0.25, "sawa": 0.25,
                "पौने": -0.25, "paune": -0.25, "pone": -0.25}
# standalone fractional numbers
_FRAC_WORDS = {"डेढ़": 1.5, "डेढ": 1.5, "dedh": 1.5, "dedth": 1.5,
               "ढाई": 2.5, "अढ़ाई": 2.5, "dhai": 2.5, "dhaai": 2.5, "adhai": 2.5}

# ordinals (irregular ones; regular ones are stem + वां/वें/वीं)
_ORDINALS = {
    "पहला": 1, "पहले": 1, "पहली": 1, "pehla": 1, "pahla": 1, "pehli": 1, "first": 1,
    "दूसरा": 2, "दूसरे": 2, "दूसरी": 2, "doosra": 2, "dusra": 2, "doosre": 2, "dusre": 2, "second": 2,
    "तीसरा": 3, "तीसरे": 3, "तीसरी": 3, "teesra": 3, "tisra": 3, "teesre": 3, "tisre": 3, "third": 3,
    "चौथा": 4, "चौथे": 4, "चौथी": 4, "chautha": 4, "chauthe": 4, "fourth": 4,
    "छठा": 6, "छठे": 6, "छठी": 6, "chhatha": 6, "chhathe": 6, "sixth": 6,
    "fifth": 5, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "twelfth": 12,
    "fourteenth": 14, "fifteenth": 15, "twentieth": 20,
}
_ORDINAL_SUFFIXES = ("वां", "वें", "वीं", "वा", "वे", "वी", "van", "ven", "vin", "va", "ve", "vi", "wan", "wen", "wa", "we")

_UNIT_WORDS = {
    "किलो": "kg", "किलोग्राम": "kg", "केजी": "kg", "kilo": "kg", "kilogram": "kg",
    "kilograms": "kg", "kg": "kg", "kgs": "kg",
    "ग्राम": "g", "gram": "g", "grams": "g", "gm": "g", "gms": "g", "g": "g",
    "डिग्री": "deg", "degree": "deg", "degrees": "deg",
    "फारेनहाइट": "F", "फ़ारेनहाइट": "F", "फॉरेनहाइट": "F", "fahrenheit": "F", "f": "F",
    "सेल्सियस": "C", "celsius": "C", "centigrade": "C", "c": "C",
}

_BP_JOINERS = {"by", "बाई", "बाय", "बटा", "over", "upon", "/"}


def _build(entries: dict) -> dict:
    return {fold(k): v for k, v in entries.items()}


_SMALL: dict[str, int] = {}
for _v, _forms in _HI_NUMBERS.items():
    for _f in _forms:
        _SMALL[fold(_f)] = _v
_SMALL.update(_build(_EN_UNITS))
_EN_TENS_F = _build(_EN_TENS)
_SMALL.update(_EN_TENS_F)
_MULT_F = _build(_MULTIPLIERS)
_POINT_F = {fold(p) for p in _POINT}
_FRAC_PREFIX_F = _build(_FRAC_PREFIX)
_FRAC_WORDS_F = _build(_FRAC_WORDS)
_ORDINALS_F = _build(_ORDINALS)
_UNIT_F = _build(_UNIT_WORDS)
_BP_JOINERS_F = {fold(j) for j in _BP_JOINERS}
_EN_UNITS_F = _build(_EN_UNITS)


# ---------------------------------------------------------------------------
# Tokeniser (spans are offsets into the original text)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"(?P<num>[0-9०-९]+(?:[.][0-9०-९]+)?)"
    r"|(?P<word>[A-Za-zऀ-ॣॱ-ॿ]+)"
    r"|(?P<slash>/)"
)


@dataclass(frozen=True)
class Token:
    kind: str  # num | word | slash
    text: str  # original text
    norm: str  # folded
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    out = []
    for m in _TOKEN_RE.finditer(text):
        kind = m.lastgroup or "word"
        out.append(Token(kind, m.group(), fold(m.group()), m.start(), m.end()))
    return out


def _ordinal_value(norm: str) -> int | None:
    if norm in _ORDINALS_F:
        return _ORDINALS_F[norm]
    for suf in _ORDINAL_SUFFIXES:
        sf = fold(suf)
        if norm.endswith(sf) and len(norm) > len(sf):
            stem = norm[: -len(sf)]
            if stem in _SMALL:
                return _SMALL[stem]
            if stem in ("नौ", "नव", "nau", "nav"):
                return 9
    return None


def word_value(norm: str) -> int | None:
    """Value of a single cardinal number word (1–99 or tens), else None."""
    return _SMALL.get(norm)


# ---------------------------------------------------------------------------
# Number parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str | None  # kg | g | deg | F | C | None
    start: int
    end: int
    text: str
    ordinal: bool = False


def _is_numberish(tok: Token) -> bool:
    n = tok.norm
    return (tok.kind == "num" or n in _SMALL or n in _MULT_F or n in _FRAC_PREFIX_F
            or n in _FRAC_WORDS_F)


def _parse_number(toks: list[Token], i: int) -> tuple[float, int, bool] | None:
    """Parse a number starting at toks[i]. Returns (value, next_index, is_ordinal)."""
    tok = toks[i]
    # digits ("120", "2.8", "१२०")
    if tok.kind == "num":
        value = float(tok.norm)
        j = i + 1
        if j < len(toks) and toks[j].norm in _MULT_F:
            value *= _MULT_F[toks[j].norm]
            j += 1
        return _maybe_decimal(toks, j, value)

    ordv = _ordinal_value(tok.norm)
    if ordv is not None and tok.norm not in _SMALL:
        return float(ordv), i + 1, True

    total = 0.0
    current = 0.0
    have = False
    frac = 0.0
    last_was_en_tens = False
    j = i
    while j < len(toks):
        n = toks[j].norm
        if n in _FRAC_PREFIX_F and j + 1 < len(toks) and toks[j + 1].norm in _SMALL:
            if have and current % 100 != 0:
                break
            frac = _FRAC_PREFIX_F[n]
            j += 1
            continue
        if n in _FRAC_WORDS_F:
            if have and current % 100 != 0:
                break
            current += _FRAC_WORDS_F[n]
            have = True
            last_was_en_tens = False
            j += 1
            continue
        if n in _SMALL:
            v = _SMALL[n]
            # Indian-English "one twenty" = 120, "one forty five" = 145
            en_hundreds = (have and total == 0 and 1 <= current <= 9 and current == int(current)
                           and j > i and toks[j - 1].norm in _EN_UNITS_F
                           and (n in _EN_TENS_F or (n in _EN_UNITS_F and v >= 10)))
            if en_hundreds:
                current = current * 100 + v
                last_was_en_tens = n in _EN_TENS_F
                j += 1
                continue
            can_add = (not have) or (current % 100 == 0 and (current or total) and frac == 0) or (
                last_was_en_tens and n in _EN_UNITS_F and v < 10)
            if not can_add:
                break
            current += v + frac
            frac = 0.0
            have = True
            last_was_en_tens = n in _EN_TENS_F
            j += 1
            continue
        if n in _MULT_F:
            m = _MULT_F[n]
            current = (current if have else 1.0) * m
            have = True
            last_was_en_tens = False
            if m >= 1000:
                total += current
                current = 0.0
            j += 1
            continue
        break
    if not have:
        return None
    return _maybe_decimal(toks, j, total + current)


def _maybe_decimal(toks: list[Token], j: int, value: float) -> tuple[float, int, bool]:
    if j + 1 < len(toks) and toks[j].norm in _POINT_F and value == int(value):
        digits = ""
        k = j + 1
        while k < len(toks):
            t = toks[k]
            if t.kind == "num" and "." not in t.norm:
                digits += t.norm
            elif t.norm in _SMALL:
                digits += str(_SMALL[t.norm])
            else:
                break
            k += 1
        if digits:
            return float(f"{int(value)}.{digits}"), k, False
    return value, j, False


def _unit_at(toks: list[Token], j: int) -> tuple[str | None, int]:
    """Read a unit (and 'degree F' style pairs) at toks[j]."""
    if j >= len(toks):
        return None, j
    u = _UNIT_F.get(toks[j].norm)
    if u is None:
        return None, j
    # bare "f"/"c"/"g" only count right after a number (we are right after a number here)
    if u == "deg" and j + 1 < len(toks) and _UNIT_F.get(toks[j + 1].norm) in ("F", "C"):
        return _UNIT_F[toks[j + 1].norm], j + 2
    return u, j + 1


def extract_quantities(text: str) -> list[Quantity]:
    """All numbers in text, with units and original spans. kg+g pairs are merged into kg."""
    toks = tokenize(text)
    out: list[Quantity] = []
    i = 0
    while i < len(toks):
        if not (_is_numberish(toks[i]) or _ordinal_value(toks[i].norm) is not None):
            i += 1
            continue
        parsed = _parse_number(toks, i)
        if parsed is None:
            i += 1
            continue
        value, j, is_ord = parsed
        unit, k = (None, j) if is_ord else _unit_at(toks, j)
        start, end = toks[i].start, toks[k - 1].end
        q = Quantity(value, unit, start, end, text[start:end], is_ord)
        # merge "2 kilo 800 gram"
        if out and unit == "g" and out[-1].unit == "kg" and _only_space_between(text, out[-1].end, start):
            prev = out.pop()
            q = Quantity(prev.value + value / 1000.0, "kg", prev.start, end, text[prev.start:end])
        out.append(q)
        i = k
    return out


def _only_space_between(text: str, a: int, b: int) -> bool:
    gap = text[a:b].strip().lower()
    return gap in ("", "aur", "और", "and")


def numbers_in(text: str) -> list[float]:
    return [q.value for q in extract_quantities(text)]


@dataclass(frozen=True)
class BloodPressure:
    systolic: int
    diastolic: int
    start: int
    end: int


def find_bp(text: str) -> list[BloodPressure]:
    """'120/80', '120 by 80', 'एक सौ बीस बटा अस्सी' → BloodPressure."""
    toks = tokenize(text)
    qs = extract_quantities(text)
    out = []
    for a, b in zip(qs, qs[1:], strict=False):
        if a.unit or b.unit:
            continue
        between = [t for t in toks if t.start >= a.end and t.end <= b.start]
        if (len(between) == 1 and between[0].norm in _BP_JOINERS_F
                and a.value == int(a.value) and b.value == int(b.value)):
            out.append(BloodPressure(int(a.value), int(b.value), a.start, b.end))
    return out


def weight_kg_candidates(text: str) -> list[float]:
    """Weight readings in kg derivable from the text."""
    qs = extract_quantities(text)
    with_unit = [q for q in qs if q.unit in ("kg", "g")]
    if with_unit:
        return [round(q.value if q.unit == "kg" else q.value / 1000.0, 3) for q in with_unit]
    return [q.value for q in qs if not q.ordinal]


def temperature_c_candidates(text: str) -> list[tuple[float, bool]]:
    """Temperatures in °C as (value, converted_from_F). Unitless 90–110 is read as °F."""
    out = []
    for q in extract_quantities(text):
        if q.ordinal:
            continue
        if q.unit == "F" or (q.unit in (None, "deg") and 90 <= q.value <= 110):
            out.append((round((q.value - 32) * 5 / 9, 1), True))
        elif q.unit in (None, "deg", "C"):
            out.append((q.value, False))
    return out


# ---------------------------------------------------------------------------
# Folded text with a map back to original offsets (for regex cue matching)
# ---------------------------------------------------------------------------


def _fold_char(ch: str) -> str:
    t = unicodedata.normalize("NFD", ch).replace(_NUKTA, "").replace(_CHANDRABINDU, _ANUSVARA)
    return t.translate(_DEV_DIGITS).lower()


def fold_with_map(text: str) -> tuple[str, list[int]]:
    """Per-character fold (NFD, no nukta, ँ→ं, ASCII digits, lowercase) plus, for each output
    character, the index of the original character it came from."""
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(unicodedata.normalize("NFC", text)):
        f = _fold_char(ch)
        out.append(f)
        idx.extend([i] * len(f))
    return "".join(out), idx


def fold_pattern(pattern: str) -> str:
    """Fold a regex written in plain Hindi/English the same way as fold_with_map."""
    return "".join(_fold_char(c) for c in pattern)
