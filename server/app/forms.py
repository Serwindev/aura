"""Form view (guided entry): a confirmed record laid out in the order of an official form, so the ASHA can
copy it or let the A.U.R.A. autofill service fill it into a form screen. Nothing is sent anywhere by this module.

Rule: a value appears only if her confirmed record (or her own saved person details) states it. "Not mentioned"
stays blank — never "No". Field order and wording come from rules/forms/*.yaml (source + status inside).

Each row has:
  value — what she reads ("2.8 kg", "Day 3", "हाँ")
  fill  — what goes into a form field ("2.8", "3", "Yes", dates as dd-mm-yyyy); None when blank
  input — text | number | date | yesno (how a form screen asks it; used by the SIMULATED targets)
  match — short label words (English + Hindi) the autofill service looks for next to a field
"""

from __future__ import annotations

import re
from datetime import date
from functools import cache

from .core.config import RULES_DIR, load_yaml

# which official forms fit a visit type (first = default)
FORMS_BY_VISIT = {
    "HBNC": ["hbnc_home_visit", "ssbsk_newborn", "ssbsk_mother", "rch_child"],
    "HBYC": ["ssbsk_child", "rch_child"],
    "IMMUNIZATION": ["rch_child"],
    "PNC": ["ssbsk_mother"],
}
FORM_IDS = ("hbnc_home_visit", "ssbsk_newborn", "ssbsk_mother", "ssbsk_child", "rch_child")
WORDS = {"en": {"yes": "Yes", "no": "No", "day": "Day", "month": "Month"},
         "hi": {"yes": "हाँ", "no": "नहीं", "day": "दिन", "month": "माह"}}
PLACE = {"institution": {"en": "Health facility", "hi": "स्वास्थ्य केंद्र"}, "home": {"en": "Home", "hi": "घर"}}
INPUT_BY_KIND = {"date": "date", "day": "number", "month": "number", "number": "number", "temp_f": "number",
                 "sign": "yesno", "vaccine": "yesno", "service": "yesno", "referral": "yesno", "dose_date": "date",
                 "person": "text", "blank": "text"}


@cache
def load_form(form_id: str) -> dict | None:
    return load_yaml(RULES_DIR / "forms" / f"{form_id}.yaml") if form_id in FORM_IDS else None


def forms_for(visit_type: str | None, person_category: str | None = None) -> list[str]:
    """Forms that fit this visit; child forms only when the visit is for a newborn/child she has saved."""
    ids = FORMS_BY_VISIT.get(visit_type or "", [])
    return [f for f in ids if not (load_form(f) or {}).get("needs_person") or person_category in ("newborn", "child")]


def _get(rec: dict, path: str):
    cur = rec
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def dmy(iso: str | date | None) -> str | None:
    if not iso:
        return None
    d = iso if isinstance(iso, date) else date.fromisoformat(str(iso))
    return d.strftime("%d-%m-%Y")


def _yes(yes: bool, lang: str) -> tuple[str, str]:
    return (WORDS[lang]["yes"] if yes else WORDS[lang]["no"]), ("Yes" if yes else "No")


def _value(item: dict, rec: dict, lang: str, ctx: dict) -> tuple[str | None, str | None]:
    """(value shown to her, value for a form field); (None, None) = blank."""
    w = WORDS[lang]
    kind = item["kind"]
    if kind == "date":
        v = _get(rec, item["path"])
        return (v, dmy(v)) if v else (None, None)
    if kind in ("day", "month"):
        v = _get(rec, item["path"])
        return (f"{w[kind]} {v}", str(v)) if v is not None else (None, None)
    if kind == "number":
        v = _get(rec, item["path"])
        if v is None:
            return None, None
        v = v * item.get("scale", 1)
        return f"{v:g} {item.get('unit', '')}".strip(), f"{v:g}"
    if kind == "temp_f":
        c = _get(rec, item["path"])
        if c is None:
            return None, None
        f = round(c * 9 / 5 + 32, 1)
        return f"{f:.1f} °F ({c:g} °C)", f"{f:.1f}"
    if kind == "sign":
        states = [d.get("present") for d in rec.get("danger_signs") or [] if d.get("code") in item["codes"]]
        if True in states:
            yes = True
        elif False in states:
            yes = False
        else:
            return None, None
        return _yes(not yes if item.get("invert") else yes, lang)
    if kind == "vaccine":
        rx = re.compile(item["rx"], re.I)
        given = any(s.get("type") == "VACCINE" and rx.search(re.sub(r"[\s-]", "", s.get("detail") or ""))
                    for s in rec.get("services_given") or [])
        return _yes(True, lang) if given else (None, None)  # not given in this note does not mean never given
    if kind == "service":
        given = any(s.get("type") in item["types"] for s in rec.get("services_given") or [])
        return _yes(True, lang) if given else (None, None)
    if kind == "referral":
        ref = rec.get("referral") or {}
        if ref.get("needed") is None:
            return None, None
        if not ref["needed"]:
            return _yes(False, lang)
        extra = [x for x in (rec.get("visit_date"), ref.get("reason"), ref.get("facility")) if x]
        return " · ".join([w["yes"], *extra]), "Yes"
    if kind == "person":
        p = ctx.get("person") or {}
        field = item["field"]
        if field == "dob":
            return (p.get("dob"), dmy(p.get("dob"))) if p.get("dob") else (None, None)
        if field == "birth_place":
            place = PLACE.get(p.get("delivery_place") or "")
            return (place[lang], place["en"]) if place else (None, None)
        v = p.get(field)
        return (v, v) if v else (None, None)
    if kind == "dose_date":
        when = (ctx.get("doses") or {}).get(item["dose"])
        return (when, dmy(when)) if when else (None, None)
    return None, None  # blank: the app does not capture this question


def _match_words(item: dict) -> list[str]:
    m = item.get("match") or {}
    return [*m.get("en", []), *m.get("hi", [])]


def form_view(rec: dict, lang: str, form_id: str | None = None, ctx: dict | None = None) -> dict | None:
    """Rows in form order for a confirmed record, or None if no form fits. ctx: {"person": {...}, "doses": {...}}
    for forms about the child (RCH child tracking)."""
    form_id = form_id or next(iter(FORMS_BY_VISIT.get(rec.get("visit_type") or "", [])), None)
    form = load_form(form_id or "")
    if form is None or (form.get("needs_person") and not (ctx or {}).get("person")):
        return None
    ctx = ctx or {}
    sections = []
    for sec in form["sections"]:
        rows = []
        for it in sec["items"]:
            value, fill = _value(it, rec, lang, ctx)
            rows.append({"id": it["id"], "question": it[lang], "label_en": it["en"], "value": value, "fill": fill,
                         "input": INPUT_BY_KIND.get(it["kind"], "text"), "match": _match_words(it),
                         "captured": it["kind"] != "blank", "note": it.get("note", {}).get(lang)})
        sections.append({"id": sec["id"], "title": sec["title"][lang], "rows": rows})
    filled = sum(1 for s in sections for r in s["rows"] if r["value"] is not None)
    total = sum(len(s["rows"]) for s in sections)
    return {"form": form_id, "title": form["title"][lang], "short": form.get("short", {}).get(lang, form["title"][lang]),
            "source": form["source"], "status": form["status"], "sections": sections, "filled": filled, "total": total}
