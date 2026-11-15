"""Edit tracking: which fields the ASHA had to correct before confirming. Synthetic data only."""

from __future__ import annotations

from tests.test_api import TODAY, login


def _note(c, h, text):
    return c.post("/v1/notes", data={"text": text, "language": "en"}, headers=h).json()


def test_counts_corrected_fields_for_her_own_notes(env):
    c = env[0]
    h = login(c)
    month = TODAY.strftime("%Y-%m")
    before = c.get(f"/v1/reports/edits?month={month}", headers=h).json()
    assert before["notes"] == 0  # demo (seed) notes are not counted

    a = _note(c, h, "Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg, no fever.")
    rec = a["record"]
    rec["vitals"]["weight_kg"] = 2.9  # she corrects the weight
    assert c.post(f"/v1/notes/{a['id']}/confirm", json={"record": rec}, headers=h).status_code == 200
    b = _note(c, h, "Visited Sunita Devi baby today, newborn visit day 3. Weight is 2.8 kg, no fever.")
    assert c.post(f"/v1/notes/{b['id']}/confirm", json={"record": b["record"]}, headers=h).status_code == 200

    s = c.get(f"/v1/reports/edits?month={month}", headers=h).json()
    assert (s["notes"], s["unchanged"]) == (2, 1)
    assert {"path": "vitals.weight_kg", "edited": 1} in s["fields"]


def test_bad_month_rejected(env):
    c = env[0]
    r = c.get("/v1/reports/edits?month=2026-13", headers=login(c))
    assert r.status_code == 422
