"""Oracle test for the claim sheet (T-054): every expected figure below is worked out by hand from
the national rates and schedule, independently of the code."""

from __future__ import annotations

from datetime import date, timedelta

from app.extraction.names import Person
from app.reports.claims import claim_sheet
from app.rules import engine
from app.services import EngineInputs

TODAY = date(2026, 11, 20)
TEMPLATE = {
    "rates": {"hbnc_series": 250, "hbyc_visit": 50},
    "hbnc_conditions": {"en": "check", "hi": "जाँच"},
    "not_computed": {"en": "n", "hi": "न"},
    "warning": {"en": "confirm UP rates", "hi": "UP"},
    "status": "x",
}


def person(pid, category, dob, place=None):
    return Person(id=pid, names=(), category=category, dob=dob, delivery_place=place, label_en=pid, label_hi=pid)


def hbnc(pid, dob, days):
    return [engine.Visit(pid, "HBNC", dob + timedelta(days=d - 1), hbnc_day=d) for d in days]


def sheet(people, visits, year=2026, month=11):
    bens = [engine.Beneficiary(p.id, p.category, p.dob, p.delivery_place) for p in people]
    return claim_sheet(people, EngineInputs(bens, visits, [], set()), TODAY, year, month, "en", TEMPLATE)


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
