"""Beneficiary name resolution v0 (T-027). Deterministic; runs AFTER validation because the
matched id is owned by code, never by the LLM.

"सुनीता की बच्ची" → the newborn whose mother is Sunita. A bare mother's name on a
child-focused visit resolves to her only child of the right age group (lower confidence).
Several different people named → the first one mentioned, confidence lowered, all candidates
returned so the review screen can offer a pick.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher

from .normalize import fold, tokenize, word_value

CHILD_WORDS = {fold(w) for w in ["बच्चे", "बच्चा", "बच्ची", "बच्चों", "बेटा", "बेटे", "बेटी", "शिशु", "नवजात", "लड़का", "लड़की", "baby", "bachche", "bachcha", "bachchi", "bacche", "baccha", "bacchi", "beta", "bete", "beti", "son", "daughter", "child"]}
POSSESSIVE = {fold(w) for w in ["के", "की", "का", "ke", "ki", "ka", "s"]}
CHILD_VISITS = {"HBNC", "HBYC", "IMMUNIZATION"}
MOTHER_VISITS = {"ANC", "PNC", "FAMILY_PLANNING"}


@dataclass(frozen=True)
class Person:
    id: str
    names: tuple[str, ...]  # any script; first token of each is the given name
    category: str  # pregnant | newborn | child | other
    mother_id: str | None = None
    dob: date | None = None
    delivery_place: str | None = None
    label_hi: str | None = None
    label_en: str | None = None
    area: str | None = None  # ward or tola she groups visits by (no GPS)
    at_risk: bool | None = None  # she marked an at-risk newborn (SSBSK schedule only)


@dataclass
class NameMatch:
    matched_id: str | None
    confidence: float
    start: int
    end: int
    candidates: list[str] = field(default_factory=list)


def _score(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if min(len(a), len(b)) < 3:
        return 0.0
    r = SequenceMatcher(None, a, b).ratio()
    return round(r * 0.9, 3) if r >= 0.85 else 0.0


def _children(people: list[Person], mother: Person, visit_type: str | None) -> list[Person]:
    kids = [p for p in people if p.mother_id == mother.id]
    if visit_type == "HBNC":
        kids = [k for k in kids if k.category == "newborn"] or kids
    return kids


def resolve_beneficiary(transcript: str, people: list[Person], visit_type: str | None = None) -> NameMatch | None:
    toks = tokenize(transcript)
    hits: list[tuple[int, float, str, int, int]] = []  # (position, score, target_id, start, end)
    for i, tok in enumerate(toks):
        if tok.kind != "word":
            continue
        for person in people:
            best = max((_score(tok.norm, fold(n.split()[0])) for n in person.names if n.strip()), default=0.0)
            if best == 0.0:
                continue
            target, end, score = person, tok.end, best
            # surname right after the given name (e.g. "पूजा यादव") — include in the span
            if i + 1 < len(toks) and any(len(n.split()) > 1 and fold(n.split()[1]) == toks[i + 1].norm
                                         for n in person.names):
                end = toks[i + 1].end
            nxt = [t.norm for t in toks[i + 1:i + 4]]
            possessive_child = (len(nxt) >= 2 and nxt[0] in POSSESSIVE and nxt[1] in CHILD_WORDS)
            # speech recognisers often drop the possessive: "rekha baby has fever"
            bare_child = len(nxt) >= 1 and nxt[0] in CHILD_WORDS
            kids = _children(people, person, visit_type)
            if (possessive_child or bare_child) and kids:
                if len(kids) == 1:
                    target, end = kids[0], toks[i + (2 if possessive_child else 1)].end
                else:
                    continue  # several children: let a child's own name decide
            elif kids and len(kids) == 1 and visit_type in CHILD_VISITS and person.category != "newborn":
                target, score = kids[0], round(best * 0.8, 3)
            hits.append((i, score, target.id, tok.start, end))
    if not hits:
        return None
    distinct = list(dict.fromkeys(h[2] for h in hits))
    first = min(hits, key=lambda h: (h[0], -h[1]))
    # a mother's name and her child's name point at the same target → not ambiguous
    conf = first[1] if len(distinct) == 1 else round(first[1] * 0.7, 3)
    return NameMatch(first[2], conf, first[3], first[4], distinct)


# ---- names not in her list (suggest "Add as new person"; never created without her tap) ------------

HOME_WORDS = {fold(w) for w in ["घर", "यहां", "यहाँ", "ghar", "yahan", "yaha", "house", "home"]}
SURNAME_WORDS = {fold(w) for w in ["देवी", "devi", "जी", "ji"]}
INTRO_BEFORE = {fold(w) for w in ["visited", "met", "named", "naam", "नाम", "name"]}
MEET_AFTER = {fold(w) for w in ["मिली", "मिले", "मिलने", "mili", "mile", "milne"]}
WITH_WORDS = {fold(w) for w in ["से", "se"]}
# common words that can sit in a name slot ("unke ghar", "visited today") — never offered as names
NOT_NAMES = {fold(w) for w in [
    "उनके", "उसके", "उनकी", "उसकी", "इनके", "इनकी", "इसके", "इसकी", "मेरे", "मेरी", "हमारे", "आपके", "अपने", "अपनी",
    "आज", "कल", "पड़ोसी", "गांव", "गाँव", "पड़ोस", "दूसरे", "दूसरी", "नए", "नई", "उन", "उस", "इन", "जिन", "किस", "सबके",
    "unke", "uske", "unki", "uski", "inke", "inki", "iske", "iski", "mere", "meri", "hamare", "aapke", "apne", "apni",
    "aaj", "kal", "padosi", "gaon", "doosre", "dusre", "nayi", "naye", "un", "us", "in", "jin", "kis",
    "the", "a", "an", "her", "his", "their", "my", "our", "your", "today", "yesterday", "again", "new", "that", "this",
    "she", "he", "they", "mother", "mom", "woman", "lady", "family", "house", "home", "visit", "visited", "newborn",
    "neighbour", "neighbor", "same", "another", "one", "first", "second", "third", "and", "with", "for", "to", "of",
    "गई", "गया", "गए", "गयी", "आई", "आया", "है", "था", "थी", "हुई", "हुआ", "दिया", "दी",
    "gayi", "gai", "gaya", "gaye", "aayi", "aai", "aaya", "hai", "tha", "thi", "hui", "hua", "diya", "di", "went", "is", "was",
]}


@dataclass
class NewName:
    text: str  # as heard, e.g. "भगवती" or "Bhagwati Devi"
    role: str  # "mother" (… ki bachchi / baby of …) | "self" (… ke ghar / visited …)
    script: str  # "hi" (Devanagari) | "en"
    start: int
    end: int


def _is_dev(s: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in s)


def _name_like(tok, people: list[Person]) -> bool:
    n = tok.norm
    if tok.kind != "word" or len(n) < 3 or n in NOT_NAMES or n in CHILD_WORDS or n in POSSESSIVE:
        return False
    if n in HOME_WORDS or n in SURNAME_WORDS or n in INTRO_BEFORE:
        return False
    if not _is_dev(tok.text) and not tok.text.isalpha():
        return False
    if word_value(n) is not None:
        return False
    # already someone in her list (same fuzzy rule the matcher uses)
    return not any(_score(n, fold(nm.split()[0])) > 0 for p in people for nm in p.names if nm.strip())


def new_names(transcript: str, people: list[Person]) -> list[NewName]:
    """Words in a name slot that are not anyone in her list: "<X> की बच्ची", "<X> ke ghar", "visited <X>",
    "baby of <X>", "<X> devi/ji", "<X> से मिली". Deterministic, narrow patterns: the ASHA confirms every
    suggestion, so a missed name only means she adds the person herself."""
    toks = tokenize(transcript)
    out: list[NewName] = []
    seen: set[str] = set()
    for i, tok in enumerate(toks):
        if not _name_like(tok, people):
            continue
        j = i + 1  # first token after the name (a "devi"/"ji" surname is part of the name)
        end = tok.end
        if j < len(toks) and toks[j].norm in SURNAME_WORDS:
            end, j = toks[j].end, j + 1
        # words after the name count only when nothing but spaces separates them ("X, baby has fever" ≠ "X baby")
        nxt = []
        last = end
        for t in toks[j:j + 2]:
            if transcript[last:t.start].strip():
                break
            nxt.append(t.norm)
            last = t.end
        prev = [t.norm for t in toks[max(0, i - 2):i]]
        pair = tuple(nxt[:2]) if len(nxt) >= 2 else ("", "")
        is_mother = ((pair[0] in POSSESSIVE and pair[1] in CHILD_WORDS)  # "X ki bachchi"
                     or (bool(nxt) and nxt[0] in CHILD_WORDS)  # "X baby"
                     or (len(prev) == 2 and prev[1] == "of" and prev[0] in CHILD_WORDS))  # "baby of X"
        is_self = ((pair[0] in POSSESSIVE and pair[1] in HOME_WORDS)  # "X ke ghar"
                   or (pair[0] in WITH_WORDS and pair[1] in MEET_AFTER)  # "X se mili"
                   or (bool(prev) and prev[-1] in INTRO_BEFORE)  # "visited X", "naam X"
                   or (len(prev) == 2 and prev[1] == "to" and prev[0] in {"visit", "went"})  # "visit to X"
                   or end != tok.end)  # "X devi" / "X ji"
        if not (is_mother or is_self):
            continue
        role = "mother" if is_mother else "self"
        text = transcript[tok.start:end]
        key = fold(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(NewName(text, role, "hi" if _is_dev(text) else "en", tok.start, end))
    return out
