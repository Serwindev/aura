"""SSBSK 2026 visit schedule as an opt-in option (D-32). The 2014/2018 schedules stay the default. Synthetic only."""

from __future__ import annotations

from datetime import date, timedelta

from app.core.config import RULES_DIR, load_yaml, validation_config
from app.rules.engine import Beneficiary, Visit, compute_tasks, load_ruleset
from tests.test_api import TODAY, login
from tests.test_people import newborn

DOB = date(2026, 11, 1)


def ids(tasks, prefix):
    return [t.rule_id for t in tasks if t.rule_id.startswith(prefix)]


def test_default_is_the_2014_schedule():
    progs = {(r["programme"], r.get("schedule")) for r in load_ruleset()}
    assert ("HBNC", None) in progs and ("HBYC", None) in progs
    assert load_ruleset(schedule="nonsense") == load_ruleset()  # unknown value falls back to the default


def test_ssbsk_files_are_sourced_drafts():
    for name in ("ssbsk_newborn.yaml", "ssbsk_child.yaml"):
        rule = load_yaml(RULES_DIR / name)
        assert "[S36]" in rule["source"] and rule["status"] == "draft"


def test_healthy_newborn_gets_days_3_7_14_42():
    tasks = compute_tasks([Beneficiary("b1", "newborn", DOB, "institution")], [], [], DOB,
                          rules=load_ruleset(schedule="ssbsk2026"))
    assert sorted(ids(tasks, "ssbsk_d")) == sorted(["ssbsk_d3", "ssbsk_d7", "ssbsk_d14", "ssbsk_d42"])
    assert not ids(tasks, "hbnc_")  # the 2014 tasks are not shown at the same time


def test_home_birth_adds_day_1():
    tasks = compute_tasks([Beneficiary("b1", "newborn", DOB, "home")], [], [], DOB, rules=load_ruleset(schedule="ssbsk2026"))
    assert "ssbsk_d1" in ids(tasks, "ssbsk_d")


def test_at_risk_newborn_gets_nine_visits_with_its_own_reason():
    tasks = compute_tasks([Beneficiary("b1", "newborn", DOB, "institution", at_risk=True)], [], [], DOB,
                          rules=load_ruleset(schedule="ssbsk2026"))
    days = sorted(int(r[len("ssbsk_d"):]) for r in ids(tasks, "ssbsk_d"))
    assert days == [1, 3, 5, 7, 10, 14, 21, 28, 42]
    assert all("at-risk" in t.reason_en for t in tasks if t.rule_id.startswith("ssbsk_d"))
    assert all(t.advisory for t in tasks)  # draft rules are never shown as authoritative


def test_at_risk_flag_is_ignored_by_the_2014_schedule():
    tasks = compute_tasks([Beneficiary("b1", "newborn", DOB, "institution", at_risk=True)], [], [], DOB)
    assert sorted(ids(tasks, "hbnc_")) == sorted(["hbnc_d3", "hbnc_d7", "hbnc_d14", "hbnc_d21", "hbnc_d28", "hbnc_d42"])


def test_child_months_run_to_36():
    tasks = compute_tasks([Beneficiary("c1", "child", date(2025, 1, 1))], [], [], date(2026, 11, 16),
                          rules=load_ruleset(schedule="ssbsk2026"))
    months = sorted(int(r[len("ssbsk_m"):]) for r in ids(tasks, "ssbsk_m"))
    assert months == [3, 6, 9, 12, 18, 24, 30, 36]


def test_recorded_hbnc_visit_ticks_the_ssbsk_task():
    visit = Visit("b1", "HBNC", DOB + timedelta(days=4), hbnc_day=5)
    tasks = compute_tasks([Beneficiary("b1", "newborn", DOB, "institution", at_risk=True)], [visit], [],
                          DOB + timedelta(days=5), rules=load_ruleset(schedule="ssbsk2026"))
    assert next(t for t in tasks if t.rule_id == "ssbsk_d5").status == "done"


def test_validation_sets_follow_the_schedule():
    assert 5 not in validation_config().hbnc_days and 21 in validation_config().hbnc_days
    ss = validation_config(schedule="ssbsk2026")
    assert {5, 10, 21} <= ss.hbnc_days  # at-risk days count
    assert {18, 24, 30, 36} <= ss.hbyc_months and 15 not in ss.hbyc_months


def test_api_switch_schedule_changes_tasks_and_confirm(env):
    c = env[0]
    h = login(c)
    assert c.get("/v1/me", headers=h).json()["schedule"] == "hbnc2014"
    assert c.patch("/v1/me", json={"schedule": "bogus"}, headers=h).status_code == 422
    pid = newborn(c, h, days=4, at_risk=True).json()["id"]
    assert c.get("/v1/beneficiaries", headers=h).json()[0]["at_risk"] in (True, False)
    me = [p for p in c.get("/v1/beneficiaries", headers=h).json() if p["id"] == pid][0]
    assert me["at_risk"] is True

    def rule_ids():
        return {t["rule_id"] for t in c.get("/v1/tasks", headers=h).json() if t["beneficiary_id"] == pid}

    assert not any(r.startswith("ssbsk_") for r in rule_ids())
    note = "Visited Kavita baby today, newborn visit day 5. Weight is 2.4 kg."
    n = c.post("/v1/notes", data={"text": note, "language": "en"}, headers=h).json()
    n["record"]["beneficiary"]["matched_id"] = pid
    r = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert r.status_code == 422  # day 5 is not on the 2014 schedule

    assert c.patch("/v1/me", json={"schedule": "ssbsk2026"}, headers=h).json()["schedule"] == "ssbsk2026"
    assert "ssbsk_d5" in rule_ids() or "ssbsk_d7" in rule_ids()
    r = c.post(f"/v1/notes/{n['id']}/confirm", json={"record": n["record"]}, headers=h)
    assert r.status_code == 200
    assert "ssbsk_d5" not in rule_ids()  # done → no longer open

    # the person flag can be cleared again
    r = c.patch(f"/v1/beneficiaries/{pid}", json={"name_hi": None, "name_en": None, "dob": me["dob"],
                                                  "delivery_place": "institution", "at_risk": False}, headers=h)
    assert r.status_code == 200 and r.json()["at_risk"] is False


def test_claim_sheet_stays_on_the_2014_rules(env):
    c = env[0]
    h = login(c)
    c.patch("/v1/me", json={"schedule": "ssbsk2026"}, headers=h)
    r = c.get(f"/v1/reports/claims?month={TODAY.isoformat()[:7]}", headers=h)
    assert r.status_code == 200
    assert "ssbsk" not in r.text.lower()
