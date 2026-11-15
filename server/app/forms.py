"""Form view (guided entry, Tier 1): a confirmed record laid out in the order of an official paper form,
so the ASHA can copy it herself. Not an integration: nothing is sent anywhere, nothing is auto-filled.

Rule: a value appears only if her confirmed record states it. "Not mentioned" stays blank — never "No".
Field order and wording come from rules/forms/*.yaml (source + status inside)."""

from __future__ import annotations

import re
from functools import cache

from .core.config import RULES_DIR, load_yaml

FORMS = {"HBNC": "hbnc_home_visit.yaml"}
WORDS = {"en": {"yes": "Yes", "no": "No", "day": "Day"}, "hi": {"yes": "हाँ", "no": "नहीं", "day": "दिन"}}


@cache
def load_form(visit_type: str) -> dict | None:
    name = FORMS.get(visit_type)
    return load_yaml(RULES_DIR / "forms" / name) if name else None


def _get(rec: dict, path: str):
    cur = rec
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _value(item: dict, rec: dict, lang: str) -> str | None:
    w = WORDS[lang]
    kind = item["kind"]
    if kind == "date":
        return _get(rec, item["path"])
    if kind == "day":
        v = _get(rec, item["path"])
        return f"{w['day']} {v}" if v is not None else None
    if kind == "number":
        v = _get(rec, item["path"])
        return f"{v:g} {item.get('unit', '')}".strip() if v is not None else None
    if kind == "temp_f":
        c = _get(rec, item["path"])
        return f"{c * 9 / 5 + 32:.1f} °F ({c:g} °C)" if c is not None else None
    if kind == "sign":
        states = [d.get("present") for d in rec.get("danger_signs") or [] if d.get("code") in item["codes"]]
        if True in states:
            yes = True
        elif False in states:
            yes = False
        else:
            return None
        if item.get("invert"):
            yes = not yes
        return w["yes"] if yes else w["no"]
    if kind == "vaccine":
        rx = re.compile(item["match"], re.I)
        given = any(s.get("type") == "VACCINE" and rx.search(re.sub(r"[\s-]", "", s.get("detail") or ""))
                    for s in rec.get("services_given") or [])
        return w["yes"] if given else None  # not given in this note does not mean never given
    if kind == "referral":
        ref = rec.get("referral") or {}
        if ref.get("needed") is None:
            return None
        if not ref["needed"]:
            return w["no"]
        extra = [x for x in (rec.get("visit_date"), ref.get("reason"), ref.get("facility")) if x]
        return " · ".join([w["yes"], *extra])
    return None  # blank: the app does not capture this question


def form_view(rec: dict, lang: str) -> dict | None:
    """Rows in form order for a confirmed record, or None if no form is configured for its visit type."""
    form = load_form(rec.get("visit_type") or "")
    if form is None:
        return None
    sections = []
    for sec in form["sections"]:
        rows = []
        for it in sec["items"]:
            note = it.get("note", {}).get(lang)
            rows.append({"id": it["id"], "question": it[lang], "value": _value(it, rec, lang),
                         "captured": it["kind"] != "blank", "note": note})
        sections.append({"id": sec["id"], "title": sec["title"][lang], "rows": rows})
    filled = sum(1 for s in sections for r in s["rows"] if r["value"] is not None)
    total = sum(len(s["rows"]) for s in sections)
    return {"title": form["title"][lang], "source": form["source"], "status": form["status"],
            "sections": sections, "filled": filled, "total": total}
