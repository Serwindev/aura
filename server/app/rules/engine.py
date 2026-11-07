"""Programme rule engine (T-050/T-051). Advisory only.

Reads rules/*.yaml and turns beneficiaries + recorded visits + doses into tasks with a
status, a priority rank and a "why now" reason. Pure function of its inputs and `today`.
The same YAML and the same test vectors (rules/tests/*.yaml) will drive the Dart port.

Status meanings:
  done      recorded visit/dose matches
  due       due date reached, still inside its window
  due_soon  due within `soon_days`
  upcoming  later than that
  overdue   window passed, not done (still worth doing)
  missed    can no longer be done (next visit fell due, or a birth dose's age limit passed)
  waiting   earlier dose in the same vaccine series not yet given
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ..core.config import RULES_DIR, load_yaml
from ..extraction.dates_hi import add_months

OPEN_STATUSES = ("overdue", "due", "due_soon")
_RANK = {"overdue": 0, "due": 1, "due_soon": 3, "upcoming": 4}


@dataclass(frozen=True)
class Beneficiary:
    id: str
    category: str  # pregnant | newborn | child | other
    dob: date | None = None
    delivery_place: str | None = None  # institution | home


@dataclass(frozen=True)
class Visit:
    beneficiary_id: str
    visit_type: str
    visit_date: date
    hbnc_day: int | None = None
    hbyc_month: int | None = None
    danger_sign: bool = False


@dataclass(frozen=True)
class DoseGiven:
    beneficiary_id: str
    dose_id: str
    given_on: date


@dataclass
class Task:
    beneficiary_id: str
    rule_id: str
    programme: str
    due_date: date
    window_end: date
    status: str
    rank: int
    reason_en: str
    reason_hi: str
    advisory: bool
    done_on: date | None = None


def load_ruleset(rules_dir: Path = RULES_DIR) -> list[dict]:
    out = []
    for name in ("hbnc.yaml", "hbyc.yaml", "uip.yaml", "anc.yaml"):
        rule = load_yaml(rules_dir / name)
        if rule.get("enabled", True):
            out.append(rule)
    return out


def _status(today: date, due: date, window_end: date, expire: date | None, soon_days: int) -> str:
    if expire is not None and today >= expire:
        return "missed"
    if today > window_end:
        return "overdue"
    if today >= due:
        return "due"
    if (due - today).days <= soon_days:
        return "due_soon"
    return "upcoming"


def _fmt(rule: dict, lang: str, **kw) -> str:
    return rule["reason"][lang].format(**kw)


def _scheduled_visits(rule: dict, b: Beneficiary, visits: list[Visit], today: date,
                      soon_days: int) -> list[Task]:
    prog = rule["programme"]
    defs = [v for v in rule["visits"]
            if all(getattr(b, k, None) == val for k, val in (v.get("only_if") or {}).items())]
    if prog == "HBNC":
        shift = 1 if rule.get("day_numbering", "birth_is_day_1") == "birth_is_day_1" else 0
        dues = [b.dob + timedelta(days=d["day"] - shift) for d in defs]
        key, vfield = "day", "hbnc_day"
    else:
        dues = [add_months(b.dob, d["month"]) for d in defs]
        key, vfield = "month", "hbyc_month"
    grace = timedelta(days=rule.get("grace_days", 0))
    mine = [v for v in visits if v.beneficiary_id == b.id and v.visit_type == prog]
    tasks = []
    for i, (d, due) in enumerate(zip(defs, dues, strict=True)):
        window_end = due + grace
        expire = dues[i + 1] if rule.get("expire_on_next") and i + 1 < len(dues) else None
        match = next((v for v in mine if getattr(v, vfield) == d[key]), None) or next(
            (v for v in mine if getattr(v, vfield) is None and due <= v.visit_date <= window_end), None)
        status = "done" if match else _status(today, due, window_end, expire, soon_days)
        kw = {key: d[key], "anchor": b.dob.isoformat()}
        tasks.append(Task(b.id, d["id"], prog, due, window_end, status, _RANK.get(status, 9),
                          _fmt(rule, "en", **kw), _fmt(rule, "hi", **kw),
                          rule["status"] != "clinician_reviewed",
                          match.visit_date if match else None))
    return tasks


def _dose_age(d: dict, dob: date) -> date:
    if "age_days" in d:
        return dob + timedelta(days=d["age_days"])
    if "age_weeks" in d:
        return dob + timedelta(weeks=d["age_weeks"])
    return add_months(dob, d["age_months"])


def _immunisation(rule: dict, b: Beneficiary, doses: list[DoseGiven], today: date,
                  soon_days: int) -> list[Task]:
    feats = rule.get("features", {})
    given = {g.dose_id: g.given_on for g in doses if g.beneficiary_id == b.id}
    defs = [d for d in rule["doses"] if feats.get(d.get("feature", ""), True)]
    by_series = {(d["series"], d["seq"]): d for d in defs if "series" in d}
    min_gap = timedelta(days=rule.get("min_interval_days", 28))
    grace = timedelta(days=rule.get("grace_days", 0))
    tasks = []
    for d in defs:
        due = _dose_age(d, b.dob)
        window_end = add_months(b.dob, d["window_end_months"]) if "window_end_months" in d else due + grace
        kw = {"vaccine": d["vaccine"], "anchor": b.dob.isoformat()}
        status = None
        if d["id"] in given:
            status = "done"
        elif "max_age_days" in d and today > b.dob + timedelta(days=d["max_age_days"]):
            status = "missed"
        elif "series" in d and d["seq"] > 1:
            prev = by_series.get((d["series"], d["seq"] - 1))
            if prev is not None:
                if prev["id"] not in given:
                    status = "waiting"
                else:
                    due = max(due, given[prev["id"]] + min_gap)
                    window_end = max(window_end, due + grace)
        if status is None:
            status = _status(today, due, window_end, None, soon_days)
        tasks.append(Task(b.id, d["id"], "UIP", due, window_end, status, _RANK.get(status, 9),
                          _fmt(rule, "en", **kw), _fmt(rule, "hi", **kw),
                          rule["status"] != "clinician_reviewed", given.get(d["id"])))
    return tasks


def compute_tasks(beneficiaries: list[Beneficiary], visits: list[Visit], doses: list[DoseGiven],
                  today: date, rules: list[dict] | None = None, soon_days: int = 7) -> list[Task]:
    rules = rules if rules is not None else load_ruleset()
    tasks: list[Task] = []
    for b in beneficiaries:
        if b.dob is None:
            continue
        for rule in rules:
            if b.category not in rule.get("applies_to", []):
                continue
            if rule["programme"] in ("HBNC", "HBYC"):
                tasks += _scheduled_visits(rule, b, visits, today, soon_days)
            elif rule["programme"] == "UIP":
                tasks += _immunisation(rule, b, doses, today, soon_days)
    _apply_danger_priority(tasks, visits)
    return sorted(tasks, key=lambda t: (t.rank, t.due_date, t.beneficiary_id, t.rule_id))


def _apply_danger_priority(tasks: list[Task], visits: list[Visit]) -> None:
    """Plan §6.1: overdue > due today > danger sign recorded > due this week."""
    latest: dict[str, Visit] = {}
    for v in visits:
        if v.beneficiary_id not in latest or v.visit_date > latest[v.beneficiary_id].visit_date:
            latest[v.beneficiary_id] = v
    flagged = {bid for bid, v in latest.items() if v.danger_sign}
    for t in tasks:
        if t.beneficiary_id in flagged and t.status in OPEN_STATUSES:
            t.reason_en += " · danger sign at last visit"
            t.reason_hi += " · पिछली बार खतरे का संकेत"
            if t.status == "due_soon":
                t.rank = 2


def open_tasks(tasks: list[Task]) -> list[Task]:
    """What the Home screen shows."""
    return [t for t in tasks if t.status in OPEN_STATUSES]
