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

from .normalize import fold, tokenize

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
