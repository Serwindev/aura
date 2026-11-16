"""Speak again on the review screen (add/change by voice) and names not in her list. Synthetic only."""

from __future__ import annotations

from app.extraction.names import new_names
from app.pipeline import load_people
from tests.test_api import NOTE, login, post_text, wav

PEOPLE = load_people()


def heard(text: str) -> list[tuple[str, str]]:
    return [(n.text, n.role) for n in new_names(text, PEOPLE)]


# ---- new names ---------------------------------------------------------------------------------

def test_new_name_child_of_unknown_mother():
    assert heard("Visited Bhagwati ki bachchi, newborn day 3") == [("Bhagwati", "mother")]
    assert heard("भगवती की बच्ची का वजन 2.8 किलो") == [("भगवती", "mother")]
    assert heard("visited the baby of Shanti today") == [("Shanti", "mother")]


def test_new_name_person_herself():
    assert heard("आज शांति देवी के घर गई") == [("शांति देवी", "self")]
    assert heard("naam Bhagwati hai") == [("Bhagwati", "self")]


def test_known_names_and_common_words_are_not_offered():
    assert heard(NOTE) == []  # Sunita Devi is in the list
    assert heard("Kavita ke ghar gayi") == []
    assert heard("unke ghar gayi, baby has fever") == []  # no name; comma breaks "gayi baby"
    assert heard("visited today, weight 3 kg") == []


def test_note_response_lists_new_names_until_she_adds_the_person(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h, text="Visited Bhagwati ki bachchi today, newborn day 3, weight 2.9 kg").json()
    assert n["new_names"] == [{"text": "Bhagwati", "role": "mother", "script": "en"}]
    assert n["record"]["beneficiary"]["matched_id"] is None  # never created or picked by itself
    r = c.post("/v1/beneficiaries", headers=h, json={"category": "newborn", "dob": "2026-11-06",
                                                     "mother_name_en": "Bhagwati", "delivery_place": "home"})
    assert r.status_code == 201
    again = c.get(f"/v1/notes/{n['id']}", headers=h).json()
    assert again["new_names"] == []


# ---- add or change by voice --------------------------------------------------------------------

def add(c, h, note_id, text):
    return c.post(f"/v1/notes/{note_id}/add", data={"text": text, "language": "en"}, headers=h)


def test_add_changes_only_what_is_said(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    assert n["record"]["vitals"]["temp_c"] == 37
    r = add(c, h, n["id"], "temperature 38 degrees, ORS given")
    assert r.status_code == 200, r.text
    m = r.json()
    rec = m["record"]
    assert rec["vitals"]["temp_c"] == 38  # newer speech wins
    assert rec["vitals"]["weight_kg"] == 2.8  # not said again → unchanged
    assert rec["beneficiary"]["matched_id"] == "c01"
    assert [s["type"] for s in rec["services_given"]] == ["ORS"]
    assert rec["evidence"]["vitals.temp_c"]["quote"] in m["transcript"]
    assert m["transcript"].startswith(NOTE) and m["transcript"].endswith("temperature 38 degrees, ORS given")
    assert m["changes"]["scalars"] == {"vitals.temp_c": 38}
    assert m["changes"]["services_given"] == [{"type": "ORS", "detail": None}]
    assert {f["path"] for f in m["flags"] if f["code"] == "VOICE_ADDED"} == {"vitals.temp_c", "services_given[0]"}
    # confirming: the voice change is the app's draft, not a correction by her
    done = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": rec}, headers=h).json()
    assert done["status"] == "confirmed"
    assert "vitals.temp_c" not in done["edited_paths"]
    assert done["record"]["evidence"]["vitals.temp_c"]["quote"] == "temperature 38 degrees"


def test_add_picks_the_person_and_clears_the_choose_flag(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h, text="newborn visit day 3, weight 2.8 kg").json()
    assert n["record"]["beneficiary"]["matched_id"] is None
    assert any(f["code"] == "NEEDS_CHOICE" and f["path"] == "beneficiary.matched_id" for f in n["flags"])
    m = add(c, h, n["id"], "this was Sunita Devi baby").json()
    assert m["record"]["beneficiary"]["matched_id"] == "c01"
    assert m["changes"]["scalars"]["beneficiary.matched_id"] == "c01"
    assert not any(f["code"] == "NEEDS_CHOICE" and f["path"] == "beneficiary.matched_id" for f in m["flags"])


def test_same_danger_sign_twice_is_one_item(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    add(c, h, n["id"], "baby has fever")
    m = add(c, h, n["id"], "baby has fever").json()
    assert [d["code"] for d in m["record"]["danger_signs"]].count("NB_FEVER") == 1


def test_add_by_audio_uses_speech_service_and_keeps_no_audio(env):
    c, cfg, stt = env
    h = login(c)
    n = post_text(c, h).json()
    stt.text = "weight 3 kg"
    r = c.post(f"/v1/notes/{n['id']}/add", data={"language": "en"}, files={"audio": ("a.wav", wav(), "audio/wav")},
               headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["record"]["vitals"]["weight_kg"] == 3
    assert r.json()["has_audio"] is False  # the typed note had no audio; the added clip is never stored
    assert not list(cfg.audio_dir.glob("*.wav")) if cfg.audio_dir.exists() else True


def test_add_nothing_new_and_wrong_states(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    assert add(c, h, n["id"], "okay that is all").json()["error"]["code"] == "NOTHING_NEW"
    assert c.post(f"/v1/notes/{n['id']}/add", data={"language": "en"}, headers=h).status_code == 422  # no input
    c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert add(c, h, n["id"], "temperature 38 degrees").status_code == 409
    other = login(c, phone="9000000009")
    assert add(c, other, n["id"], "temperature 38 degrees").status_code == 404
