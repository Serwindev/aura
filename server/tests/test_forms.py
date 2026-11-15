"""Form view: a confirmed record in official form order. Blank stays blank. Synthetic data only."""

from __future__ import annotations

from app.forms import form_view
from tests.test_api import login


def _rec(**kw):
    rec = {"visit_type": "HBNC", "visit_date": "2026-11-12", "visit_index": {"hbnc_day": 3},
           "vitals": {"weight_kg": 2.8, "temp_c": 37.5}, "danger_signs": [], "services_given": [],
           "referral": {"needed": None, "facility": None, "reason": None}}
    rec.update(kw)
    return rec


def _rows(view):
    return {r["id"]: r for s in view["sections"] for r in s["rows"]}


def test_values_in_form_order_and_fahrenheit():
    v = form_view(_rec(), "en")
    rows = _rows(v)
    assert [s["id"] for s in v["sections"]] == ["head", "A", "B", "C", "D", "E"]
    assert rows["day"]["value"] == "Day 3"
    assert rows["C2"]["value"] == "2.8 kg"
    assert rows["C3"]["value"] == "99.5 °F (37.5 °C)"


def test_not_mentioned_is_blank_never_no():
    rows = _rows(form_view(_rec(), "en"))
    for k in ("A5", "C4", "C5", "D1", "E2", "E6"):
        assert rows[k]["value"] is None, k
    assert rows["A1"]["captured"] is False


def test_signs_vaccines_and_referral():
    rec = _rec(danger_signs=[{"code": "NB_NOT_FEEDING", "present": True}, {"code": "NB_JAUNDICE", "present": False}],
               services_given=[{"type": "VACCINE", "detail": "OPV-0"}, {"type": "VACCINE", "detail": "Hep B birth dose"}],
               referral={"needed": True, "facility": "CHC", "reason": "not feeding"})
    rows = _rows(form_view(rec, "hi"))
    assert rows["E2"]["value"] == "हाँ"
    assert rows["A5"]["value"] == "नहीं"  # "fed properly?" is the inverse of "not feeding"
    assert rows["C4"]["value"] == "नहीं"  # stated absent
    assert (rows["C5"]["value"], rows["C6"]["value"], rows["C7"]["value"]) == (None, "हाँ", "हाँ")
    assert rows["D1"]["value"] == "हाँ · 2026-11-12 · not feeding · CHC"


def test_other_visit_types_have_no_form():
    assert form_view(_rec(visit_type="IMMUNIZATION"), "en") is None


def test_endpoint_needs_confirmed_own_note(env):
    c = env[0]
    h = login(c)
    n = c.post("/v1/notes", data={"text": "Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg.",
                                  "language": "en"}, headers=h).json()
    assert c.get(f"/v1/notes/{n['id']}/form", headers=h).json()["error"]["code"] == "NOT_CONFIRMED"
    assert c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).status_code == 200
    v = c.get(f"/v1/notes/{n['id']}/form?lang=en", headers=h).json()
    assert _rows(v)["C2"]["value"] == "2.8 kg" and v["filled"] >= 3
    other = login(c, phone="9000000077")
    assert c.get(f"/v1/notes/{n['id']}/form", headers=other).status_code == 404
