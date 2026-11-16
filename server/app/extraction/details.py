"""Extra form details from speech (D-39): "aankh mein mawad nahin" → eyes_pus = No, with the clause as its quote.

Deterministic keyword rules over rules/forms/details.yaml — no LLM. The text is split into clauses (punctuation,
"aur/and/but/lekin"); a detail is answered only from a clause that contains one of its topic words:
  yesno          → Yes, or No if a negation word is in the clause ("nahin", "no", "not")
  yesno+problem  → needs a problem word (pus, swelling…) → Yes/No as above; or a "fine" word (theek, normal) → No
  number         → the first number after the topic word in that clause (unit fixes: °C→°F, g→kg)
  choice         → the first option whose word is in the clause (sex: boy/girl…)
  text           → digits after the topic word (RCH IDs)
The ASHA sees every proposed value with its quote and confirms it; nothing is saved by this module."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from ..core.config import RULES_DIR, load_yaml
from .normalize import extract_quantities, fold, normalize_for_match

NEG = {fold(w) for w in ["नहीं", "नही", "न", "ना", "nahi", "nahin", "nhi", "nahee", "na", "no", "not", "never", "without",
                         "बिना", "bina", "koi nahi"]}
FINE = {fold(w) for w in ["ठीक", "theek", "thik", "normal", "fine", "ok", "okay", "साफ़", "साफ", "saaf", "सामान्य", "samanya",
                          "clear", "clean"]}
_SPLIT = re.compile(r"[.,;:!?।|\n]+|\s(?:aur|और|and|but|lekin|लेकिन|par|पर|magar|मगर|also|bhi)\s", re.I)


@dataclass(frozen=True)
class Detail:
    id: str
    value: bool | float | str
    quote: str


@cache
def catalog() -> dict[str, dict]:
    return load_yaml(RULES_DIR / "forms" / "details.yaml")["details"]


def ids_for(scope: str) -> list[str]:
    return [k for k, v in catalog().items() if v["scope"] == scope]


def common_for(visit_type: str | None) -> list[str]:
    return [k for k, v in catalog().items() if visit_type and visit_type in (v.get("common_for") or [])]


def _clauses(text: str) -> list[tuple[int, int]]:
    out, start = [], 0
    for m in _SPLIT.finditer(text):
        if m.start() > start:
            out.append((start, m.start()))
        start = m.end()
    if start < len(text):
        out.append((start, len(text)))
    return [(a, b) for a, b in out if text[a:b].strip()]


def _words(d: dict, key: str) -> list[str]:
    v = d.get(key) or {}
    return [*v.get("en", []), *v.get("hi", [])] if isinstance(v, dict) else list(v)


def _find(clause_norm: str, words: list[str]) -> int:
    """Position of the first word/phrase (word-boundary match on normalised text), or -1."""
    best = -1
    padded = f" {clause_norm} "
    for w in words:
        nw = normalize_for_match(w)
        if not nw:
            continue
        i = padded.find(f" {nw} ")
        if i < 0 and len(nw) >= 4:  # Hindi postpositions glue on: "आँखों" contains "आँख" — allow a prefix match
            m = re.search(r"(?:^| )" + re.escape(nw), padded)
            i = m.start() if m else -1
        if i >= 0 and (best < 0 or i < best):
            best = i
    return best


def _has(clause_norm: str, words: set[str]) -> bool:
    toks = clause_norm.split()
    joined = f" {clause_norm} "
    return any(w in toks or (" " in w and f" {w} " in joined) for w in words)


def _answer(d: dict, clause: str) -> bool | float | str | None:
    norm = normalize_for_match(clause)
    pos = _find(norm, _words(d, "topic"))
    if pos < 0:
        return None
    t = d["type"]
    if t == "yesno":
        neg = _has(norm, NEG)
        if d.get("problem"):
            if _find(norm, _words(d, "problem")) >= 0:
                return not neg
            return False if _has(norm, FINE) else None
        yes = not neg
        if d.get("invert_words") and _find(norm, list(d["invert_words"])) >= 0:
            yes = not yes
        return yes
    if t == "number":
        nums = [q for q in extract_quantities(clause) if not q.ordinal]
        # prefer a number said after the topic word ("mother temperature 99"); pos is in normalised text
        after = [q for q in nums if len(normalize_for_match(clause[:q.start])) >= pos - 1] or nums
        if not after:
            return None
        q = after[0]
        v = q.value
        if d.get("unit") == "°F" and (q.unit == "C" or v < 45):
            v = round(v * 9 / 5 + 32, 1)
        if d.get("unit") == "kg" and (q.unit == "g" or v > 100):
            v = v / 1000
        lo, hi = d.get("range", [None, None])
        if lo is not None and not (lo <= v <= hi):
            return None
        return round(v, 2)
    if t == "choice":
        for key, opt in d["options"].items():
            if _find(norm, opt["words"]) >= 0:
                return key
        return None
    if t == "text":
        if d.get("not_after") and _find(norm, d["not_after"]) >= 0:
            return None
        m = re.search(r"\d[\d \-]{4,}\d", clause)
        return re.sub(r"[ \-]", "", m.group()) if m else None
    return None


def extract_details(text: str, only: list[str] | None = None) -> list[Detail]:
    """Details stated in text. Later clauses win ("eyes fine … sorry, eyes have pus" → Yes)."""
    found: dict[str, Detail] = {}
    ids = only if only is not None else ids_for("visit")
    for a, b in _clauses(text):
        clause = text[a:b].strip()
        for did in ids:
            d = catalog().get(did)
            if d is None:
                continue
            v = _answer(d, clause)
            if v is not None:
                found[did] = Detail(did, v, clause)
    return list(found.values())


def check_value(did: str, value) -> str | None:
    """Error message if a value does not fit the detail's type, else None."""
    d = catalog().get(did)
    if d is None:
        return "Unknown detail"
    t = d["type"]
    if t == "yesno" and not isinstance(value, bool):
        return "Choose Yes or No"
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "Enter a number"
        lo, hi = d.get("range", [None, None])
        if lo is not None and not (lo <= value <= hi):
            return f"Expected {lo}–{hi}"
    if t == "choice" and value not in d["options"]:
        return "Choose one option"
    if t == "text" and (not isinstance(value, str) or not value.strip() or len(value) > 40):
        return "Enter a short text"
    return None


def detail_label(did: str, lang: str) -> str:
    d = catalog()[did]
    return d[lang]


def display(did: str, value, lang: str) -> tuple[str, str]:
    """(shown, fill) for a stored value."""
    d = catalog()[did]
    t = d["type"]
    if t == "yesno":
        yes = {"en": "Yes", "hi": "हाँ"}[lang] if value else {"en": "No", "hi": "नहीं"}[lang]
        return yes, "Yes" if value else "No"
    if t == "number":
        unit = d.get("unit", "")
        return f"{value:g} {unit}".strip(), f"{value:g}"
    if t == "choice":
        opt = d["options"][value]
        return opt[lang], opt["en"]
    return str(value), str(value)
