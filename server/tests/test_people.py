"""Adding people (T-045): the ASHA registers a newborn, child or pregnant woman herself. Synthetic only."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests.test_api import TODAY, login


def add(c, h, **body):
    return c.post("/v1/beneficiaries", json=body, headers=h)


def newborn(c, h, days=2, **extra):
    body = {"category": "newborn", "dob": (TODAY - timedelta(days=days)).isoformat(),
            "mother_name_hi": "कविता", "mother_name_en": "Kavita", "delivery_place": "institution", **extra}
    return add(c, h, **body)


def test_add_unnamed_newborn_with_new_mother_gets_tasks(env):
    c = env[0]
    h = login(c)
    r = newborn(c, h)
    assert r.status_code == 201
    p = r.json()
    assert p["own"] and p["id"].startswith("p-")
    assert p["label"] == "कविता का बच्चा"  # default UI language is Hindi
    assert p["mother_label"] == "कविता"
    tasks = [t for t in c.get("/v1/tasks", headers=h).json() if t["beneficiary_id"] == p["id"]]
    assert any(t["programme"] == "HBNC" for t in tasks)


def test_voice_style_note_matches_the_new_baby(env):
    c = env[0]
    h = login(c)
    pid = newborn(c, h).json()["id"]
    note = "आज कविता के बच्चे का नवजात भ्रमण दिन 3 किया, वजन 2 किलो 900 ग्राम है।"
    n = c.post("/v1/notes", data={"text": note, "language": "hi"}, headers=h).json()
    assert n["record"]["beneficiary"]["matched_id"] == pid
    assert n["record"]["vitals"]["weight_kg"] == 2.9


def test_english_name_works_for_english_notes(env):
    c = env[0]
    h = login(c)
    pid = add(c, h, category="child", name_en="Aarav", name_hi="आरव",
              dob=(TODAY - timedelta(days=100)).isoformat()).json()["id"]
    n = c.post("/v1/notes", data={"text": "Aarav vaccination done, Penta 2 given today.", "language": "en"},
               headers=h).json()
    assert n["record"]["beneficiary"]["matched_id"] == pid


def test_remove_demo_keeps_people_she_added(env):
    c = env[0]
    h = login(c)
    pid = newborn(c, h).json()["id"]
    c.post("/v1/demo", json={"action": "remove"}, headers=h)
    ids = {p["id"] for p in c.get("/v1/beneficiaries", headers=h).json()}
    assert pid in ids
    mother = next(p for p in c.get("/v1/beneficiaries", headers=h).json() if p["id"] == pid)["mother_id"]
    assert mother in ids  # her mother stays too


def test_pregnant_woman_has_no_birth_details(env):
    c = env[0]
    h = login(c)
    p = add(c, h, category="pregnant", name_hi="ममता", name_en="Mamta", dob=TODAY.isoformat(),
            delivery_place="home").json()
    assert (p["dob"], p["delivery_place"], p["label"]) == (None, None, "ममता")


@pytest.mark.parametrize(("body", "code"), [
    ({"category": "newborn", "name_en": "X"}, "DOB_REQUIRED"),
    ({"category": "newborn", "name_en": "X", "dob": (TODAY + timedelta(days=1)).isoformat()}, "DOB_IN_FUTURE"),
    ({"category": "newborn", "name_en": "X", "dob": (TODAY - timedelta(days=90)).isoformat()}, "NOT_NEWBORN"),
    ({"category": "child", "name_en": "X", "dob": (TODAY - timedelta(days=7 * 366)).isoformat()}, "TOO_OLD"),
    ({"category": "newborn", "dob": TODAY.isoformat()}, "NAME_REQUIRED"),
    ({"category": "alien", "name_en": "X"}, "BAD_CATEGORY"),
    ({"category": "newborn", "name_en": "X", "dob": TODAY.isoformat(), "mother_id": "c01"}, "BAD_MOTHER"),
    ({"category": "newborn", "name_en": "X", "dob": TODAY.isoformat(), "delivery_place": "moon"}, "BAD_PLACE"),
    ({"category": "other", "name_en": "x" * 61}, "NAME_TOO_LONG"),
])
def test_bad_input_rejected(env, body, code):
    c = env[0]
    r = add(c, login(c), **body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code


def test_duplicate_rejected(env):
    c = env[0]
    h = login(c)
    mother = add(c, h, category="other", name_en="Kavita").json()["id"]
    body = {"category": "newborn", "dob": TODAY.isoformat(), "mother_id": mother}
    assert add(c, h, **body).status_code == 201
    r = add(c, h, **body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "PERSON_EXISTS"


def test_edit_own_person_but_not_demo(env):
    c = env[0]
    h = login(c)
    pid = newborn(c, h).json()["id"]
    r = c.patch(f"/v1/beneficiaries/{pid}", json={"name_en": "Diya", "name_hi": "दीया",
                                                  "dob": (TODAY - timedelta(days=3)).isoformat()}, headers=h)
    assert r.status_code == 200 and r.json()["label"] == "दीया"
    assert r.json()["dob"] == (TODAY - timedelta(days=3)).isoformat()
    assert c.patch("/v1/beneficiaries/c01", json={"name_en": "Hack"}, headers=h).status_code == 404


def test_delete_blocked_when_notes_or_children_exist(env):
    c = env[0]
    h = login(c)
    p = newborn(c, h).json()
    assert c.delete(f"/v1/beneficiaries/{p['mother_id']}", headers=h).json()["error"]["code"] == "PERSON_IN_USE"
    c.post("/v1/notes", data={"text": "आज कविता के बच्चे का नवजात भ्रमण किया।", "language": "hi"}, headers=h)
    assert c.delete(f"/v1/beneficiaries/{p['id']}", headers=h).status_code == 409
    spare = add(c, h, category="other", name_en="Spare").json()["id"]
    assert c.delete(f"/v1/beneficiaries/{spare}", headers=h).status_code == 200
    assert spare not in {x["id"] for x in c.get("/v1/beneficiaries", headers=h).json()}


def test_people_belong_to_their_owner(env):
    c = env[0]
    pid = newborn(c, login(c)).json()["id"]
    other = login(c, phone="9000000077")
    assert pid not in {x["id"] for x in c.get("/v1/beneficiaries", headers=other).json()}
    assert c.delete(f"/v1/beneficiaries/{pid}", headers=other).status_code == 404


def test_export_includes_people_added(env):
    c = env[0]
    h = login(c)
    pid = newborn(c, h).json()["id"]
    added = c.get("/v1/privacy/export", headers=h).json()["people_added"]
    assert pid in {p["id"] for p in added}


def test_area_set_inherited_and_shown_on_tasks(env):
    c = env[0]
    h = login(c)
    p = newborn(c, h, area="  Naya   tola ").json()
    assert p["area"] == "Naya tola"
    mother = next(x for x in c.get("/v1/beneficiaries", headers=h).json() if x["id"] == p["mother_id"])
    assert mother["area"] == "Naya tola"  # the new mother was added in the same area
    assert {t["area"] for t in c.get("/v1/tasks", headers=h).json() if t["beneficiary_id"] == p["id"]} == {"Naya tola"}
    r = c.patch(f"/v1/beneficiaries/{p['id']}", json={"area": "", "dob": p["dob"]}, headers=h)
    assert r.json()["area"] is None
    assert add(c, h, category="other", name_en="Y", area="x" * 41).json()["error"]["code"] == "AREA_TOO_LONG"


def test_demo_people_have_invented_areas_shared_by_mother_and_child(env):
    c = env[0]
    people = c.get("/v1/beneficiaries", headers=login(c)).json()
    by_id = {p["id"]: p for p in people}
    assert all(p["area"] for p in people)
    assert all(p["area"] == by_id[p["mother_id"]]["area"] for p in people if p["mother_id"] in by_id)


def test_old_database_gets_area_column(tmp_path):
    import sqlite3

    from app.db.models import make_session_factory
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE people (owner_id VARCHAR, id VARCHAR, names JSON, category VARCHAR, mother_id VARCHAR,"
                " dob DATE, delivery_place VARCHAR, label_hi VARCHAR, label_en VARCHAR, PRIMARY KEY (owner_id, id))")
    con.commit()
    con.close()
    make_session_factory(f"sqlite:///{db}")
    cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(people)")}
    assert "area" in cols
