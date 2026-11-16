"""More official forms (SSBSK, RCH child tracking), fill values for autofill, and the SIMULATED practice portal.
Synthetic data only."""

from __future__ import annotations

import pytest

from app.forms import FORM_IDS, INPUT_BY_KIND, form_view, load_form
from tests.test_api import login
from tests.test_forms import _rec, _rows

NOTE = "Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg, temperature 37 degrees."


def confirmed(c, h, text=NOTE):
    n = c.post("/v1/notes", data={"text": text, "language": "en"}, headers=h).json()
    r = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("form_id", FORM_IDS)
def test_every_answerable_row_has_label_words_for_autofill(form_id):
    form = load_form(form_id)
    assert form["source"] and form["status"] == "draft"
    for sec in form["sections"]:
        for it in sec["items"]:
            assert it["kind"] in INPUT_BY_KIND, it["id"]
            if it["kind"] != "blank":
                assert isinstance(it.get("match"), dict) and it["match"].get("en"), f"{form_id}.{it['id']} has no match words"


def test_fill_values_are_bare_and_blank_stays_blank():
    rows = _rows(form_view(_rec(), "hi"))
    assert (rows["date"]["fill"], rows["day"]["fill"], rows["C2"]["fill"], rows["C3"]["fill"]) == ("12-11-2026", "3", "2.8", "99.5")
    assert rows["C2"]["value"] == "2.8 kg"  # what she reads stays as before
    assert rows["A1"]["fill"] is None and rows["C4"]["fill"] is None
    assert rows["C2"]["input"] == "number" and rows["C4"]["input"] == "yesno" and rows["date"]["input"] == "date"
    assert "weight" in rows["C2"]["match"] and "वज़न" in rows["C2"]["match"]


def test_ssbsk_newborn_weight_in_grams_and_signs():
    rec = _rec(danger_signs=[{"code": "NB_FEVER", "present": True}], services_given=[{"type": "COUNSELLING", "detail": None}])
    rows = _rows(form_view(rec, "en", "ssbsk_newborn"))
    assert rows["weight"]["value"] == "2800 g" and rows["weight"]["fill"] == "2800"
    assert rows["d_hot"]["fill"] == "Yes" and rows["counsel"]["fill"] == "Yes"
    assert rows["d_cold"]["fill"] is None  # not said → blank, never "No"


def test_forms_list_and_rch_child_tracking_from_person_and_confirmed_doses(env):
    c = env[0]
    h = login(c)
    note = confirmed(c, h)
    forms = c.get(f"/v1/notes/{note['id']}/forms?lang=en", headers=h).json()
    assert [f["id"] for f in forms] == ["hbnc_home_visit", "ssbsk_newborn", "ssbsk_mother", "rch_child"]
    confirmed(c, h, "Sunita Devi baby got Penta 1 vaccine today")
    v = c.get(f"/v1/notes/{note['id']}/form?lang=en&form=rch_child", headers=h).json()
    rows = _rows(v)
    assert rows["mother"]["fill"] == "Sunita Devi"
    assert rows["dob"]["fill"] == "08-11-2026"  # synthetic register date
    assert rows["place"]["fill"] == "Health facility"
    assert rows["bcg"]["fill"] == "08-11-2026"  # SIMULATED demo history: BCG at birth
    assert rows["penta1"]["fill"] == "09-11-2026"  # date of her confirmed note that gave Penta-1
    assert rows["mr1"]["fill"] is None
    assert rows["sex"]["fill"] is None  # not captured
    bad = c.get(f"/v1/notes/{note['id']}/form?form=ssbsk_child", headers=h)
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "NO_FORM"


def test_rch_form_needs_a_saved_child():
    assert form_view(_rec(visit_type="IMMUNIZATION"), "en") is None  # no person context → no RCH form


def test_practice_portal_is_labelled_simulated_and_has_a_login_box(env):
    c = env[0]
    idx = c.get("/sim-portal/")
    assert idx.status_code == 200 and "SIMULATED" in idx.text and "/sim-portal/rch_child" in idx.text
    for fid in FORM_IDS:
        page = c.get(f"/sim-portal/{fid}")
        assert page.status_code == 200 and "SIMULATED" in page.text and "not a government website" in page.text
        assert 'type="password"' in page.text
        assert 'name="fld1"' in page.text  # field names are not A.U.R.A. ids: autofill must use labels
    assert "Weight (grams) / वज़न (ग्राम)" in c.get("/sim-portal/ssbsk_newborn").text
    assert "No such form" in c.get("/sim-portal/nope").text
