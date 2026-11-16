"""Extra form details (D-39), reopening and editing confirmed notes. Synthetic data only."""

from __future__ import annotations

from app.extraction.details import common_for, extract_details, ids_for
from tests.test_api import login, post_text

NOTE = "Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg, temperature 37 degrees."


def got(text, only=None):
    return {d.id: d.value for d in extract_details(text, only)}


# ---- voice rules ---------------------------------------------------------------------------------

def test_yes_no_with_negation_problem_words_and_fine_words():
    assert got("Baby is alive, eyes have no pus, only breast milk.") == {"baby_alive": True, "eyes_pus": False, "exclusive_bf": True}
    assert got("बच्चा जीवित है। आँखों में मवाद नहीं है, सिर्फ़ माँ का दूध पी रहा है।") == {
        "baby_alive": True, "eyes_pus": False, "exclusive_bf": True}
    assert got("aankh theek hai aur upar ka doodh bhi diya") == {"eyes_pus": False, "exclusive_bf": False}
    assert got("nipples are cracked and painful, baby kept warm") == {"nipple_problem": True, "kept_warm": True}
    assert got("the eyes look at the mother") == {}  # topic word without a problem or fine word: no answer


def test_numbers_with_unit_fixes():
    assert got("Mother temperature 99") == {"mother_temp_f": 99}
    assert got("माँ का तापमान 37 डिग्री") == {"mother_temp_f": 98.6}  # °C said → stored as °F
    assert got("height 74 cm") == {"height_cm": 74}
    assert got("height 400 cm") == {}  # out of range → not proposed


def test_ordinary_note_has_no_extra_details_and_later_clause_wins():
    assert got(NOTE) == {}
    assert got("eyes are fine. sorry, eyes have pus") == {"eyes_pus": True}


def test_person_details_only_when_asked():
    text = "It is a girl, birth weight 2700 grams, RCH ID 1234 5678 9012, mother's RCH 998877665544"
    assert got(text) == {}  # person details are never taken from an ordinary note
    assert got(text, ids_for("person")) == {"sex": "female", "birth_weight_kg": 2.7, "rch_id": "123456789012",
                                            "mother_rch_id": "998877665544"}


def test_common_details_per_visit_type():
    assert {"baby_alive", "exclusive_bf", "eyes_pus", "mother_temp_f"} <= set(common_for("HBNC"))
    assert "height_cm" in common_for("HBYC") and common_for(None) == []


# ---- in notes ------------------------------------------------------------------------------------

def test_note_captures_details_with_quotes_and_confirm_checks_them(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h, text=NOTE + " Eyes have no pus, only breast milk.").json()
    rec = n["record"]
    assert rec["extras"] == {"eyes_pus": False, "exclusive_bf": True}
    assert rec["evidence"]["extras.eyes_pus"]["quote"] == "Eyes have no pus"
    bad = dict(rec, extras={"eyes_pus": "maybe"})
    r = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": bad}, headers=h).json()
    assert r["error"]["details"][0]["path"] == "extras.eyes_pus"
    unknown = dict(rec, extras={"favourite_colour": True})
    assert c.post(f"/v1/notes/{n['id']}/confirm", json={"record": unknown}, headers=h).status_code == 422
    rec["extras"]["baby_alive"] = True  # she tapped Yes on the review card
    done = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": rec}, headers=h).json()
    assert done["record"]["extras"] == {"eyes_pus": False, "exclusive_bf": True, "baby_alive": True}
    assert "extras.baby_alive" in done["edited_paths"] and "extras.eyes_pus" not in done["edited_paths"]


def test_voice_add_on_review_fills_details(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    m = c.post(f"/v1/notes/{n['id']}/add", data={"text": "mother temperature 99, baby kept warm", "language": "en"},
               headers=h).json()
    assert m["record"]["extras"] == {"mother_temp_f": 99, "kept_warm": True}
    assert m["changes"]["scalars"] == {"extras.mother_temp_f": 99, "extras.kept_warm": True}


# ---- reopen and edit ------------------------------------------------------------------------------

def test_recent_visits_and_one_persons_visits(env):
    c = env[0]
    h = login(c)
    a = post_text(c, h).json()
    c.post(f"/v1/notes/{a['id']}/confirm", json={"record": a["record"]}, headers=h)
    post_text(c, h, text="Visited Rekha baby today, newborn visit day 7")  # stays a draft
    recent = c.get("/v1/notes?status=confirmed&limit=20", headers=h).json()
    assert [x["id"] for x in recent] == [a["id"]] and recent[0]["status"] == "confirmed"
    assert [x["id"] for x in c.get("/v1/notes?status=confirmed&beneficiary_id=c01", headers=h).json()] == [a["id"]]
    assert c.get("/v1/notes?status=confirmed&beneficiary_id=c02", headers=h).json() == []


def test_edit_a_confirmed_note_and_confirm_again(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    first = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).json()
    assert c.post(f"/v1/notes/{n['id']}/edit", headers=h).status_code == 200
    rec = first["record"]
    rec["vitals"]["weight_kg"] = 2.9
    # a plain repeat confirm (e.g. a retry) changes nothing
    same = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": rec}, headers=h).json()
    assert same["record"]["vitals"]["weight_kg"] == 2.8
    done = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": rec, "edit": True}, headers=h).json()
    assert done["status"] == "confirmed" and done["record"]["vitals"]["weight_kg"] == 2.9
    assert "vitals.weight_kg" in done["edited_paths"] and "vitals.weight_kg" not in done["record"]["evidence"]
    assert done["record"]["evidence"]["vitals.temp_c"]["quote"]  # untouched fields keep their quote
    draft = post_text(c, h, text="Visited Rekha baby today, newborn visit day 7").json()
    assert c.post(f"/v1/notes/{draft['id']}/edit", headers=h).json()["error"]["code"] == "NOT_CONFIRMED"


# ---- details missing from a form ------------------------------------------------------------------

def test_form_lists_missing_details_voice_proposes_and_save_fills(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    rch = c.get(f"/v1/notes/{n['id']}/form?lang=en&form=rch_child", headers=h).json()
    assert {"sex", "birth_weight_kg", "rch_id", "mother_rch_id", "exclusive_bf"} <= set(rch["missing"])
    said = "It is a girl, birth weight 2700 grams, child RCH ID 1234 5678 9012, eyes no pus"
    r = c.post(f"/v1/notes/{n['id']}/details/voice", headers=h,
               data={"text": said, "language": "en", "wanted": ",".join(rch["missing"])}).json()
    props = {p["id"]: p for p in r["proposals"]}
    assert props["sex"]["value"] == "female" and props["birth_weight_kg"]["value"] == 2.7
    assert "eyes_pus" not in props  # not asked by this form
    values = {k: v["value"] for k, v in props.items()} | {"mother_rch_id": "998877665544", "exclusive_bf": True}
    quotes = {k: v["quote"] for k, v in props.items()} | {"exclusive_bf": "words she never said"}
    saved = c.post(f"/v1/notes/{n['id']}/details", json={"values": values, "quotes": quotes}, headers=h)
    assert saved.status_code == 200, saved.text
    ev = saved.json()["record"]["evidence"]
    assert "extras.exclusive_bf" not in ev  # a quote not in the transcript is dropped
    rows = {r["id"]: r for s in c.get(f"/v1/notes/{n['id']}/form?lang=en&form=rch_child", headers=h).json()["sections"]
            for r in s["rows"]}
    assert (rows["sex"]["fill"], rows["bw"]["fill"], rows["rch_id"]["fill"], rows["mother_rch"]["fill"]) == (
        "Girl", "2.7", "123456789012", "998877665544")
    assert rows["ebf6"]["fill"] == "Yes" and rows["sex"]["missing"] is False
    people = {p["id"]: p for p in c.get("/v1/beneficiaries", headers=h).json()}
    assert people["c01"]["sex"] == "female" and people["w01"]["rch_id"] == "998877665544"
    bad = c.post(f"/v1/notes/{n['id']}/details", json={"values": {"birth_weight_kg": 40}}, headers=h)
    assert bad.status_code == 422
    nothing = c.post(f"/v1/notes/{n['id']}/details/voice", headers=h, data={"text": "okay", "language": "en"})
    assert nothing.json()["error"]["code"] == "NOTHING_NEW"
