"""Oracle test for the claim sheet (T-054): every expected figure below is worked out by hand from
the national rates and schedule, independently of the code."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from app.extraction.names import Person
from app.reports.claims import claim_sheet
from app.rules import engine
from app.services import EngineInputs

TODAY = date(2026, 11, 20)
TEMPLATE = {
    "rates": {"hbnc_series": 250, "hbyc_visit": 50},
    "not_computed": {"en": "n", "hi": "न"},
    "warning": {"en": "confirm UP rates", "hi": "UP"},
    "status": "x",
}


def person(pid, category, dob, place=None, checked=True):
    """checked: she confirmed both HBNC payment conditions (True), neither (None), or a condition failed (False)."""
    return Person(id=pid, names=(), category=category, dob=dob, delivery_place=place, label_en=pid, label_hi=pid,
                  safe_d42=checked, birth_registered=checked)


def hbnc(pid, dob, days):
    return [engine.Visit(pid, "HBNC", dob + timedelta(days=d - 1), hbnc_day=d) for d in days]


def sheet(people, visits, year=2026, month=11, lang="en"):
    bens = [engine.Beneficiary(p.id, p.category, p.dob, p.delivery_place) for p in people]
    return claim_sheet(people, EngineInputs(bens, visits, [], set()), TODAY, year, month, lang, TEMPLATE)


def rows(s, programme):
    return {(r["beneficiary_id"], r["detail"]): r for r in s["rows"] if r["programme"] == programme}


INSTITUTION_DAYS = [3, 7, 14, 21, 28, 42]


def test_complete_series_finishing_this_month_pays_once():
    dob = date(2026, 10, 1)  # day 42 = 11 Nov
    s = sheet([person("a", "newborn", dob, "institution")], hbnc("a", dob, INSTITUTION_DAYS))
    r = rows(s, "HBNC")[("a", "6/6")]
    assert (r["status"], r["amount"]) == ("ready", 250)
    assert s["total"] == 250


def test_complete_series_finished_last_month_is_not_this_months_claim():
    dob = date(2026, 9, 1)  # day 42 = 12 Oct
    s = sheet([person("a", "newborn", dob, "institution")], hbnc("a", dob, INSTITUTION_DAYS))
    assert rows(s, "HBNC") == {} and s["total"] == 0


def test_home_delivery_needs_seven_visits():
    dob = date(2026, 10, 1)
    s = sheet([person("a", "newborn", dob, "home")], hbnc("a", dob, INSTITUTION_DAYS))
    r = rows(s, "HBNC")[("a", "6/7")]
    assert (r["status"], r["amount"]) == ("missing_visit", 0)
    full = sheet([person("a", "newborn", dob, "home")], hbnc("a", dob, [1, *INSTITUTION_DAYS]))
    assert rows(full, "HBNC")[("a", "7/7")]["amount"] == 250


def test_missed_visit_blocks_payment():
    dob = date(2026, 10, 1)
    s = sheet([person("a", "newborn", dob, "institution")], hbnc("a", dob, [3, 7, 21, 28, 42]))  # no day 14
    r = rows(s, "HBNC")[("a", "5/6")]
    assert (r["status"], r["amount"]) == ("missing_visit", 0)


def test_series_still_running_is_in_progress():
    dob = date(2026, 11, 15)  # day 3 = 17 Nov done; day 7 = 21 Nov not yet
    s = sheet([person("a", "newborn", dob, "institution")], hbnc("a", dob, [3]))
    r = rows(s, "HBNC")[("a", "1/6")]
    assert (r["status"], r["amount"]) == ("in_progress", 0)


def test_hbyc_pays_per_visit_done_this_month():
    dob = date(2026, 8, 5)  # 3 months = 5 Nov
    s = sheet([person("b", "child", dob)], [engine.Visit("b", "HBYC", date(2026, 11, 5), hbyc_month=3)])
    r = rows(s, "HBYC")[("b", "3")]
    assert (r["status"], r["amount"]) == ("ready", 50)


def test_hbyc_due_this_month_not_done_pays_nothing():
    dob = date(2026, 8, 25)  # 3 months = 25 Nov, still ahead of TODAY
    s = sheet([person("b", "child", dob)], [])
    r = rows(s, "HBYC")[("b", "3")]
    assert (r["status"], r["amount"]) == ("in_progress", 0)


def test_total_adds_hbnc_and_hbyc():
    d1, d2 = date(2026, 10, 1), date(2026, 8, 5)
    s = sheet([person("a", "newborn", d1, "institution"), person("b", "child", d2)],
              [*hbnc("a", d1, INSTITUTION_DAYS), engine.Visit("b", "HBYC", date(2026, 11, 5), hbyc_month=3)])
    assert s["total"] == 250 + 50


# ---- payment conditions and "what to do" (hand-worked from the national rule [S17]) ----

def test_finished_series_waits_for_her_condition_checks():
    dob = date(2026, 10, 1)
    s = sheet([person("a", "newborn", dob, "institution", checked=None)], hbnc("a", dob, INSTITUTION_DAYS))
    r = rows(s, "HBNC")[("a", "6/6")]
    assert (r["status"], r["amount"], r["pending"]) == ("check_conditions", 0, 250)
    assert (s["total"], s["pending"]) == (0, 250)
    assert r["checks"] == {"safe_d42": None, "birth_registered": None}
    assert "mother and baby safe at day 42" in r["todo"][0] and "birth registered" in r["todo"][0]


def test_one_condition_confirmed_still_waits_for_the_other():
    dob = date(2026, 10, 1)
    p = replace(person("a", "newborn", dob, "institution", checked=None), safe_d42=True)
    r = rows(sheet([p], hbnc("a", dob, INSTITUTION_DAYS)), "HBNC")[("a", "6/6")]
    assert r["status"] == "check_conditions"
    assert "birth registered" in r["todo"][0] and "safe" not in r["todo"][0]


def test_failed_condition_is_not_payable():
    dob = date(2026, 10, 1)
    p = replace(person("a", "newborn", dob, "institution"), birth_registered=False)
    s = sheet([p], hbnc("a", dob, INSTITUTION_DAYS))
    r = rows(s, "HBNC")[("a", "6/6")]
    assert (r["status"], r["amount"], r["pending"], s["total"]) == ("not_eligible", 0, 0, 0)
    assert r["todo"] == ["Not payable: birth not registered."]


def test_missed_visit_says_which_and_when():
    dob = date(2026, 10, 1)  # birth = day 1, so day 14 = 14 Oct
    s = sheet([person("a", "newborn", dob, "institution")], hbnc("a", dob, [3, 7, 21, 28, 42]))
    r = rows(s, "HBNC")[("a", "5/6")]
    assert r["todo"] == ["Missed: day 14 visit (was due 14 Oct). The series is incomplete; ask your ANM."]


def test_running_series_says_next_visit():
    dob = date(2026, 11, 15)  # day 7 = 21 Nov
    r = rows(sheet([person("a", "newborn", dob, "institution")], hbnc("a", dob, [3])), "HBNC")[("a", "1/6")]
    assert r["todo"] == ["Next: day 7 visit on 21 Nov."]
    assert r["checks"] is None


def test_hbyc_due_row_says_when_in_hindi():
    dob = date(2026, 8, 25)  # 3 months = 25 Nov
    r = rows(sheet([person("b", "child", dob)], [], lang="hi"), "HBYC")[("b", "3")]
    assert r["todo"] == ["अगला: माह 3 का भ्रमण, 25/11 को।"]
