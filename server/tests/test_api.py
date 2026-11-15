"""End-to-end API tests: login → note → confirm → tasks → claim sheet → privacy. Synthetic only."""

from __future__ import annotations

import io
import wave
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.settings import load_settings
from app.main import create_app
from app.stt.providers import MockStt

TODAY = date(2026, 11, 9)
NOTE = "Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg, temperature 37 degrees."


def wav(seconds: float = 0.5) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * seconds))
    return buf.getvalue()


@pytest.fixture
def env(tmp_path):
    cfg = load_settings(tmp_path)
    cfg.today_override = TODAY
    stt = MockStt(NOTE)
    return TestClient(create_app(cfg, stt=stt, warm_stt=False)), cfg, stt


def login(client, phone="9000000001"):
    otp = client.post("/v1/auth/otp/request", json={"phone": phone}).json()
    assert otp["simulated"] is True
    r = client.post("/v1/auth/otp/verify", json={"phone": phone, "otp": otp["otp"], "asha_id": "DEMO-1", "name": "Demo"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


def post_text(client, h, text=NOTE, **form):
    return client.post("/v1/notes", data={"text": text, "language": "en", **form}, headers=h)


def test_requires_login(env):
    assert env[0].get("/v1/tasks").status_code == 401
    assert env[0].get("/v1/tasks", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_wrong_otp_locks_after_attempts(env):
    c = env[0]
    c.post("/v1/auth/otp/request", json={"phone": "9000000002"})
    for _ in range(5):
        assert c.post("/v1/auth/otp/verify", json={"phone": "9000000002", "otp": "bad"}).json()["error"]["code"] == "OTP_WRONG"
    assert c.post("/v1/auth/otp/verify", json={"phone": "9000000002", "otp": "bad"}).json()["error"]["code"] == "OTP_EXPIRED"


def test_bad_phone_rejected(env):
    assert env[0].post("/v1/auth/otp/request", json={"phone": "123"}).status_code == 422


def test_text_note_is_draft_with_evidence(env):
    c = env[0]
    r = post_text(c, login(c))
    assert r.status_code == 201
    n = r.json()
    assert n["status"] == "draft"
    assert n["record"]["visit_type"] == "HBNC"
    assert n["record"]["beneficiary"]["matched_id"] == "c01"
    assert n["record"]["vitals"]["weight_kg"] == 2.8
    assert n["record"]["evidence"]["vitals.weight_kg"]["quote"] in NOTE


def test_idempotent_create(env):
    c = env[0]
    h = login(c)
    a = post_text(c, h, idempotency_key="k1").json()
    b = post_text(c, h, idempotency_key="k1").json()
    assert a["id"] == b["id"]


def test_queued_note_keeps_its_recording_date(env):
    """A note spoken offline yesterday and sent today: "today" in the note means yesterday."""
    c = env[0]
    h = login(c)
    spoken = (TODAY - timedelta(days=1)).isoformat()
    n = post_text(c, h, recorded_on=spoken, idempotency_key="q1").json()
    assert n["recorded_on"] == spoken
    assert n["record"]["visit_date"] == spoken


def test_recorded_on_defaults_to_server_today(env):
    c = env[0]
    n = post_text(c, login(c)).json()
    assert n["recorded_on"] == TODAY.isoformat()


def test_recorded_on_in_future_is_clamped_to_today(env):
    c = env[0]
    n = post_text(c, login(c), recorded_on=(TODAY + timedelta(days=2)).isoformat()).json()
    assert n["recorded_on"] == TODAY.isoformat()
    assert n["record"]["visit_date"] == TODAY.isoformat()


@pytest.mark.parametrize(("value", "code"), [("09-11-2026", "BAD_RECORDED_ON"),
                                             ((TODAY - timedelta(days=61)).isoformat(), "RECORDED_ON_TOO_OLD")])
def test_recorded_on_rejected(env, value, code):
    c = env[0]
    r = post_text(c, login(c), recorded_on=value)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code


def test_needs_exactly_one_input(env):
    c = env[0]
    h = login(c)
    assert c.post("/v1/notes", data={"language": "en"}, headers=h).status_code == 422
    r = c.post("/v1/notes", data={"text": "x", "language": "en"}, files={"audio": ("a.wav", wav(), "audio/wav")}, headers=h)
    assert r.status_code == 422


def test_audio_kept_until_confirm_then_deleted(env):
    c, cfg, _ = env
    h = login(c)
    n = c.post("/v1/notes", data={"language": "en"}, files={"audio": ("a.wav", wav(), "audio/wav")}, headers=h).json()
    assert n["has_audio"] and n["stt_provider"].startswith("mock")
    assert len(list(cfg.audio_dir.glob("*.wav"))) == 1
    assert c.get(f"/v1/notes/{n['id']}/audio", headers=h).status_code == 200
    done = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).json()
    assert done["status"] == "confirmed" and done["audio_deleted"] is True and done["has_audio"] is False
    assert list(cfg.audio_dir.glob("*.wav")) == []


def test_discard_deletes_audio(env):
    c, cfg, _ = env
    h = login(c)
    n = c.post("/v1/notes", data={"language": "en"}, files={"audio": ("a.wav", wav(), "audio/wav")}, headers=h).json()
    assert c.post(f"/v1/notes/{n['id']}/discard", headers=h).json()["status"] == "discarded"
    assert list(cfg.audio_dir.glob("*.wav")) == []


def test_non_wav_rejected(env):
    c = env[0]
    r = c.post("/v1/notes", data={"language": "en"}, files={"audio": ("a.wav", b"not audio", "audio/wav")}, headers=login(c))
    assert r.status_code == 415


def test_silence_gives_clear_error(env):
    c, _, stt = env
    stt.text = ""
    r = c.post("/v1/notes", data={"language": "en"}, files={"audio": ("a.wav", wav(), "audio/wav")}, headers=login(c))
    assert r.json()["error"]["code"] == "EMPTY_TRANSCRIPT"


def test_nothing_is_confirmed_without_explicit_call(env):
    c = env[0]
    h = login(c)
    before = c.get("/v1/tasks", headers=h).json()
    post_text(c, h)
    assert c.get("/v1/tasks", headers=h).json() == before
    assert c.get("/v1/notes?status=confirmed", headers=h).json() == []


def test_confirm_requires_choices(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h, text="someone was visited today").json()
    assert {f["path"] for f in n["flags"] if f["severity"] == "error"} >= {"visit_type", "beneficiary.matched_id"}
    r = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert r.status_code == 422
    assert {d["path"] for d in r.json()["error"]["details"]} >= {"visit_type", "beneficiary.matched_id"}


@pytest.mark.parametrize("change, path", [
    (lambda r: r["vitals"].update(weight_kg=50), "vitals.weight_kg"),
    (lambda r: r.update(visit_date=(TODAY + timedelta(days=1)).isoformat()), "visit_date"),
    (lambda r: r["vitals"].update(bp_sys=70, bp_dia=90), "vitals.bp_sys"),
    (lambda r: r["visit_index"].update(hbnc_day=5), "visit_index.hbnc_day"),
    (lambda r: r.update(danger_signs=[{"code": "MADE_UP", "present": True}]), "danger_signs[0]"),
])
def test_confirm_revalidates_edits(env, change, path):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    change(n["record"])
    r = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert r.status_code == 422
    assert path in {d["path"] for d in r.json()["error"]["details"]}


def test_unknown_field_rejected(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    n["record"]["surprise"] = 1
    assert c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).status_code == 422


def test_edit_drops_evidence_and_client_cannot_forge_it(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    n["record"]["vitals"]["weight_kg"] = 3.1
    n["record"]["evidence"]["vitals.pulse"] = {"quote": "forged"}
    done = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).json()
    assert "vitals.weight_kg" in done["edited_paths"]
    assert "vitals.weight_kg" not in done["record"]["evidence"]
    assert "vitals.pulse" not in done["record"]["evidence"]
    assert "vitals.temp_c" in done["record"]["evidence"]


def test_repeat_confirm_does_not_overwrite(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()
    first = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).json()
    n["record"]["vitals"]["weight_kg"] = 3.3
    again = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).json()
    assert again["record"]["vitals"]["weight_kg"] == first["record"]["vitals"]["weight_kg"] == 2.8


def test_users_cannot_see_each_other(env):
    c = env[0]
    a, b = login(c), login(c, "9000000003")
    n = post_text(c, a).json()
    assert c.get(f"/v1/notes/{n['id']}", headers=b).status_code == 404
    assert c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=b).status_code == 404


def test_home_tasks_have_reasons_and_advisory(env):
    c = env[0]
    tasks = c.get("/v1/tasks", headers=login(c)).json()
    assert tasks
    assert all(t["reason"] and t["advisory"] is True for t in tasks)
    statuses = [t["status"] for t in tasks]
    assert statuses == sorted(statuses, key=["overdue", "due", "due_soon"].index) or "overdue" in statuses


def test_seeded_overdue_vaccine_clears_when_confirmed(env):
    c = env[0]
    h = login(c)
    assert any(t["id"] == "c08:mr1" for t in c.get("/v1/tasks", headers=h).json())
    n = post_text(c, h, text="Ishaan vaccination done, MR 1 given today").json()
    assert n["record"]["services_given"][0]["detail"] == "MR-1"
    c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert not any(t["id"] == "c08:mr1" for t in c.get("/v1/tasks", headers=h).json())


def test_task_hint_fills_person_and_type(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h, text="weight 3 kg", beneficiary_id="c07", programme="HBNC", rule_id="hbnc_d14").json()
    assert n["record"]["beneficiary"]["matched_id"] == "c07"
    assert n["record"]["visit_type"] == "HBNC" and n["record"]["visit_index"]["hbnc_day"] == 14
    assert not [f for f in n["flags"] if f["severity"] == "error"]


def test_task_mismatch_warns_and_keeps_spoken_name(env):
    c = env[0]
    h = login(c)
    n = post_text(c, h, beneficiary_id="c07", programme="HBNC", rule_id="hbnc_d14").json()
    assert n["record"]["beneficiary"]["matched_id"] == "c01"
    assert any(f["code"] == "TASK_MISMATCH" for f in n["flags"])


def test_unnumbered_vaccine_asks_for_dose(env):
    c = env[0]
    n = post_text(c, login(c), text="Aarav vaccination, penta given today").json()
    assert any(f["code"] == "NEEDS_DOSE" for f in n["flags"])


def test_danger_sign_survives_missing_visit_type(env):
    c = env[0]
    n = post_text(c, login(c), text="Rekha baby has fever and is not feeding.").json()
    assert {d["code"] for d in n["record"]["danger_signs"]} == {"NB_FEVER", "NB_NOT_FEEDING"}
    assert all(d["present"] for d in n["record"]["danger_signs"])


def test_hbnc_without_day_asks_for_it(env):
    c = env[0]
    n = post_text(c, login(c), text="Rekha baby newborn visit done, weight 3 kg").json()
    assert any(f["code"] == "NEEDS_DAY" and f["path"] == "visit_index.hbnc_day" for f in n["flags"])


def test_spoken_english_day_number(env):
    c = env[0]
    n = post_text(c, login(c), text="sunita baby newborn visit day seven weight two point eight kilo").json()
    assert n["record"]["visit_index"]["hbnc_day"] == 7
    assert n["record"]["vitals"]["weight_kg"] == 2.8


def test_vaccine_implies_immunisation_visit(env):
    c = env[0]
    n = post_text(c, login(c), text="Penta 2 was given to Aarav").json()
    assert n["record"]["visit_type"] == "IMMUNIZATION"
    assert n["record"]["services_given"][0]["detail"] == "Penta-2"


def test_dismiss_reschedule_restore(env):
    c = env[0]
    h = login(c)
    ids = lambda: {t["id"] for t in c.get("/v1/tasks", headers=h).json()}  # noqa: E731
    url = "/v1/tasks/c08/mr1/action"
    assert "c08:mr1" in ids()
    c.post(url, json={"action": "dismiss"}, headers=h)
    assert "c08:mr1" not in ids()
    c.post(url, json={"action": "restore"}, headers=h)
    assert "c08:mr1" in ids()
    assert c.post(url, json={"action": "reschedule", "until": TODAY.isoformat()}, headers=h).status_code == 422
    c.post(url, json={"action": "reschedule", "until": (TODAY + timedelta(days=2)).isoformat()}, headers=h)
    assert "c08:mr1" not in ids()


def test_claim_sheet_demo_month(env):
    c = env[0]
    s = c.get("/v1/reports/claims?month=2026-11&lang=en", headers=login(c)).json()
    ready = {(r["programme"], r["beneficiary_id"]): r for r in s["rows"] if r["status"] == "ready"}
    assert ready[("HBNC", "c20")]["amount"] == 250 and ready[("HBNC", "c20")]["seeded"] is True
    assert ready[("HBNC", "c20")]["detail"] == "6/6"
    assert "confirm UP rates" in s["warning"]
    assert s["total"] == sum(r["amount"] for r in s["rows"])


def test_exports_are_valid_files(env):
    c = env[0]
    h = login(c)
    for lang in ("hi", "en"):
        pdf = c.get(f"/v1/reports/claims?month=2026-11&format=pdf&lang={lang}", headers=h)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        x = c.get(f"/v1/reports/claims?month=2026-11&format=xlsx&lang={lang}", headers=h)
        assert x.status_code == 200 and x.content[:2] == b"PK"


def test_privacy_export_and_delete(env):
    c, cfg, _ = env
    h = login(c)
    n = c.post("/v1/notes", data={"language": "en"}, files={"audio": ("a.wav", wav(), "audio/wav")}, headers=h).json()
    s = c.get("/v1/privacy/summary", headers=h).json()
    assert s["draft_notes"] == 1 and s["audio_files"] == 1 and "location" in s["never_collected"]
    assert any(x["id"] == n["id"] for x in c.get("/v1/privacy/export", headers=h).json()["notes"])
    assert c.delete("/v1/privacy/data", headers=h).status_code == 200
    s = c.get("/v1/privacy/summary", headers=h).json()
    assert s["draft_notes"] == 0 and s["audio_files"] == 0
    assert list(cfg.audio_dir.glob("*.wav")) == []


def test_only_microphone_permission_header(env):
    p = env[0].get("/v1/meta").headers["Permissions-Policy"]
    assert "microphone=(self)" in p and "geolocation=()" in p and "camera=()" in p
