"""Sarvam adapter (mocked HTTP; no network, no credits) and the monthly report export."""

from __future__ import annotations

import io
import json
import os

import httpx
import pytest
from openpyxl import load_workbook

from app.core.settings import load_dotenv
from app.stt.base import SttError, Transcript
from app.stt.providers import SARVAM_URL, MockStt, SarvamStt, get_stt, keyterms, split_pcm

from .test_api import env, login, post_text, wav  # noqa: F401  (fixture re-use)


def client_returning(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sarvam_sends_wav_language_model_and_keyterms():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"request_id": "x", "transcript": "रेखा के बच्चे का वजन 2.8 किलो",
                                         "language_code": "hi-IN"})

    stt = SarvamStt(api_key="test-key", client=client_returning(handler))
    tr = stt.transcribe(wav(2.0), "hi", hints=["रेखा"])
    assert tr.text == "रेखा के बच्चे का वजन 2.8 किलो"
    assert tr.provider == "sarvam-saaras-v4"
    req = seen[0]
    assert str(req.url) == SARVAM_URL
    assert req.headers["api-subscription-key"] == "test-key"
    body = req.content.decode("utf-8", "replace")
    for part in ('name="model"', "saaras:v4", 'name="language_code"', "hi-IN", 'name="keyterms"', "रेखा", "RIFF"):
        assert part in body


def test_long_audio_is_split_under_30_seconds_and_joined():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(len(req.content))
        return httpx.Response(200, json={"transcript": f"part{len(calls)}"})

    stt = SarvamStt(api_key="k", client=client_returning(handler))
    tr = stt.transcribe(wav(65.0), "en")
    assert len(calls) == 3
    assert tr.text == "part1 part2 part3"


def test_split_pcm_cuts_at_quiet_point_and_keeps_all_audio():
    loud, quiet = b"\x00\x40" * 16000, b"\x00\x00" * 16000  # 1 s each
    pcm = loud * 20 + quiet + loud * 20  # 41 s, silence at 20-21 s
    parts = split_pcm(pcm)
    assert len(parts) == 2
    assert all(len(p) / 2 / 16000 < 30 for p in parts)
    assert sum(len(p) for p in parts) == len(pcm)
    assert 20 <= len(parts[0]) / 2 / 16000 <= 21


def test_network_failure_falls_back_offline_and_says_so():
    def handler(req):
        raise httpx.ConnectError("no internet")

    stt = SarvamStt(api_key="k", client=client_returning(handler), fallback=MockStt("offline words"))
    tr = stt.transcribe(wav(1.0), "en")
    assert tr.text == "offline words"
    assert "offline fallback" in tr.provider


def test_bad_key_is_an_error_not_a_silent_fallback():
    def handler(req):
        return httpx.Response(403, json={"error": {"code": "invalid_api_key_error", "message": "bad key"}})

    stt = SarvamStt(api_key="k", client=client_returning(handler), fallback=MockStt("x"))
    with pytest.raises(SttError, match="invalid_api_key_error"):
        stt.transcribe(wav(1.0), "en")


def test_keyterms_limits():
    terms = keyterms([f"name{i}" for i in range(80)] + ["x" * 100])
    assert len(terms) == 50 and all(len(t) <= 64 for t in terms)
    assert keyterms(None)[0] == "ASHA"


def test_auto_provider_picks_sarvam_only_with_key(monkeypatch):
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    monkeypatch.setenv("SARVAM_API_KEY", "k")
    assert isinstance(get_stt(), SarvamStt)
    monkeypatch.setenv("SARVAM_API_KEY", "")
    assert get_stt("mock").name == "mock"


def test_dotenv_never_overrides_existing(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# c\nAURA_T1=from_file\nAURA_T2='quoted'\nAURA_T3=\n", encoding="utf-8")
    monkeypatch.setenv("AURA_T1", "already")
    monkeypatch.delenv("AURA_T2", raising=False)
    monkeypatch.delenv("AURA_T3", raising=False)
    load_dotenv(f)
    assert os.environ["AURA_T1"] == "already"
    assert os.environ["AURA_T2"] == "quoted"
    assert "AURA_T3" not in os.environ


def test_pipeline_passes_register_names_as_hints(env):  # noqa: F811
    c, _cfg, stt = env
    got = {}

    def spy(wav_bytes, language="hi", hints=None):
        got["hints"] = hints
        return Transcript("Rekha baby day 7 weight 2.8 kg", "spy")

    stt.transcribe = spy
    r = c.post("/v1/notes", files={"audio": ("n.wav", wav(1.0), "audio/wav")}, data={"language": "en"},
               headers=login(c))
    assert r.status_code == 201
    assert "Rekha" in got["hints"] and all(h.isascii() for h in got["hints"])


# ---- monthly report --------------------------------------------------------------------------

def test_monthly_report_json_counts_confirmed_visits(env):  # noqa: F811
    c = env[0]
    h = login(c)
    before = c.get("/v1/reports/monthly?month=2026-11&lang=en", headers=h).json()
    n = post_text(c, h).json()
    assert c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h).status_code == 200
    rep = c.get("/v1/reports/monthly?month=2026-11&lang=en", headers=h).json()
    assert len(rep["visits"]) == len(before["visits"]) + 1
    mine = [v for v in rep["visits"] if not v["simulated"]]
    assert mine[0]["beneficiary_id"] == "c01" and mine[0]["weight_kg"] == 2.8 and mine[0]["source"] == "Typed"
    total = {r["label"]: r["value"] for r in rep["summary"]}
    assert total["Visits recorded"] == len(rep["visits"])
    assert total["Estimated incentive (₹)"] == rep["claims"]["total"]
    assert all(v["source"].endswith("(SIMULATED)") for v in rep["visits"] if v["simulated"])


def test_monthly_report_pdf_and_excel(env):  # noqa: F811
    c = env[0]
    h = login(c)
    for lang in ("hi", "en"):
        pdf = c.get(f"/v1/reports/monthly?month=2026-11&format=pdf&lang={lang}", headers=h)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert "aura-monthly-report-2026-11.pdf" in pdf.headers["content-disposition"]
        x = c.get(f"/v1/reports/monthly?month=2026-11&format=xlsx&lang={lang}", headers=h)
        assert x.status_code == 200
        wb = load_workbook(io.BytesIO(x.content))
        assert wb.sheetnames == ["Summary", "Visits", "Tasks", "Incentive"]
        assert wb["Visits"].max_row >= 2


def test_monthly_report_rejects_bad_input_and_needs_login(env):  # noqa: F811
    c = env[0]
    h = login(c)
    assert c.get("/v1/reports/monthly?month=2026-13", headers=h).status_code == 422
    assert c.get("/v1/reports/monthly?format=doc", headers=h).status_code == 422
    assert c.get("/v1/reports/monthly").status_code == 401


def test_empty_month_report_still_renders(env):  # noqa: F811
    c = env[0]
    h = login(c)
    rep = c.get("/v1/reports/monthly?month=2025-01&lang=hi", headers=h).json()
    assert rep["visits"] == [] and json.dumps(rep)
    assert c.get("/v1/reports/monthly?month=2025-01&format=pdf&lang=hi", headers=h).content.startswith(b"%PDF")


# ---- demo data toggle ------------------------------------------------------------------------

def test_new_login_gets_small_demo(env):  # noqa: F811
    c = env[0]
    h = login(c)
    d = c.get("/v1/demo", headers=h).json()
    assert d["active"] is True and d["beneficiaries"] == 6
    ids = {p["id"] for p in c.get("/v1/beneficiaries", headers=h).json()}
    assert {"c01", "c02", "c07", "c08", "c20", "w03"} <= ids
    assert {"w01", "w02", "w07", "w08", "w20"} <= ids  # mothers, so "Rekha's baby" resolves
    assert len(ids) == 11


def test_remove_demo_keeps_own_notes_and_their_people(env):  # noqa: F811
    c = env[0]
    h = login(c)
    n = post_text(c, h).json()  # about c01, Sunita's baby
    c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    d = c.post("/v1/demo", json={"action": "remove"}, headers=h).json()
    assert d == {"active": False, "demo_people": 0, "demo_notes": 0, "beneficiaries": 0}
    assert {p["id"] for p in c.get("/v1/beneficiaries", headers=h).json()} == {"c01", "w01"}
    rep = c.get("/v1/reports/monthly?month=2026-11&lang=en", headers=h).json()
    assert len(rep["visits"]) == 1 and not rep["visits"][0]["simulated"]
    assert c.get("/v1/reports/claims?month=2026-11&lang=en", headers=h).json()["total"] == 0
    assert c.get("/v1/privacy/summary", headers=h).json()["confirmed_notes"] == 1


def test_load_demo_again_is_idempotent(env):  # noqa: F811
    c = env[0]
    h = login(c)
    first = c.get("/v1/demo", headers=h).json()
    c.post("/v1/demo", json={"action": "remove"}, headers=h)
    again = c.post("/v1/demo", json={"action": "load"}, headers=h).json()
    assert again == first
    assert c.post("/v1/demo", json={"action": "load"}, headers=h).json() == first  # nothing doubled
    assert c.post("/v1/demo", json={"action": "nope"}, headers=h).status_code == 422
    assert c.post("/v1/demo", json={"action": "load"}).status_code == 401
