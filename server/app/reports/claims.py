"""Incentive claim SUPPORT sheet (T-054). Advisory estimate at configured rates: prepares a claim,
never files one. A pure function of the engine's tasks, so it can be checked against an oracle."""

from __future__ import annotations

from datetime import date

from ..core.config import REPO_ROOT, load_yaml
from ..extraction.names import Person
from ..rules import engine

TEMPLATE_PATH = REPO_ROOT / "templates" / "UP" / "claim_support.yaml"
OVERDUE = ("overdue", "missed")


def load_template() -> dict:
    return load_yaml(TEMPLATE_PATH)


def _in_month(d: date | None, year: int, month: int) -> bool:
    return d is not None and (d.year, d.month) == (year, month)


def _label(p: Person, lang: str) -> str:
    return (p.label_hi if lang == "hi" else p.label_en) or p.label_en or p.id


def claim_sheet(people: list[Person], inputs, today: date, year: int, month: int, lang: str,
                template: dict | None = None) -> dict:
    tpl = template or load_template()
    rates = tpl["rates"]
    tasks = engine.compute_tasks(inputs.beneficiaries, inputs.visits, inputs.doses, today)
    by_person = {p.id: p for p in people}
    rows: list[dict] = []

    def is_seeded(bid: str, programme: str, dates: list[date]) -> bool:
        return bool(dates) and all((bid, programme, d) in inputs.seeded_visits for d in dates)

    for bid in sorted({t.beneficiary_id for t in tasks}):
        p = by_person[bid]
        hbnc = [t for t in tasks if t.beneficiary_id == bid and t.programme == "HBNC"]
        done = [t for t in hbnc if t.status == "done"]
        dates = sorted(t.done_on for t in done)
        if hbnc and len(done) == len(hbnc):
            if _in_month(dates[-1], year, month):
                rows.append(_row("HBNC", p, lang, f"{len(done)}/{len(hbnc)}", dates, "ready",
                                 rates["hbnc_series"], tpl["hbnc_conditions"][lang],
                                 is_seeded(bid, "HBNC", dates)))
        elif hbnc and (any(_in_month(t.done_on, year, month) for t in done)
                       or any(_in_month(t.due_date, year, month) for t in hbnc)):
            status = "missing_visit" if any(t.status in OVERDUE for t in hbnc) else "in_progress"
            rows.append(_row("HBNC", p, lang, f"{len(done)}/{len(hbnc)}", dates, status, 0, "",
                             is_seeded(bid, "HBNC", dates)))
        for t in tasks:
            if t.beneficiary_id != bid or t.programme != "HBYC":
                continue
            month_no = t.rule_id.removeprefix("hbyc_m")
            if t.status == "done" and _in_month(t.done_on, year, month):
                rows.append(_row("HBYC", p, lang, month_no, [t.done_on], "ready", rates["hbyc_visit"], "",
                                 is_seeded(bid, "HBYC", [t.done_on])))
            elif t.status != "done" and _in_month(t.due_date, year, month):
                rows.append(_row("HBYC", p, lang, month_no, [],
                                 "missing_visit" if t.status in OVERDUE else "in_progress", 0, "", False))

    order = {"ready": 0, "missing_visit": 1, "in_progress": 2}
    rows.sort(key=lambda r: (order[r["status"]], r["programme"], r["label"]))
    return {"month": f"{year:04d}-{month:02d}", "rows": rows, "total": sum(r["amount"] for r in rows),
            "warning": tpl["warning"][lang], "not_computed": tpl["not_computed"][lang],
            "status": tpl["status"], "generated_on": today.isoformat()}


def _row(programme: str, p: Person, lang: str, detail: str, dates: list[date], status: str, amount: int,
         conditions: str, seeded: bool) -> dict:
    return {"programme": programme, "beneficiary_id": p.id, "label": _label(p, lang), "detail": detail,
            "dates": [d.isoformat() for d in dates], "status": status, "amount": amount,
            "conditions": conditions, "seeded": seeded}
