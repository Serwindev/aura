"""Incentive claim SUPPORT sheet (T-054). Advisory estimate at configured rates: prepares a claim,
never files one. A pure function of the engine's tasks (plus her own condition checks on the child), so it
can be checked against an oracle.

Each row says what to do next: which visit was missed or is late, which visit comes next, and, for a finished
HBNC series, the two payment conditions [S17] she still has to confirm (mother and baby safe at day 42; birth
registered). A series is counted in the total only when both conditions are confirmed."""

from __future__ import annotations

from datetime import date

from ..core.config import REPO_ROOT, load_yaml
from ..extraction.names import Person
from ..rules import engine

TEMPLATE_PATH = REPO_ROOT / "templates" / "UP" / "claim_support.yaml"
OVERDUE = ("overdue", "missed")
STATUS_ORDER = {"ready": 0, "check_conditions": 1, "missing_visit": 2, "in_progress": 3, "not_eligible": 4}
CHECKS = ("safe_d42", "birth_registered")

TEXT = {
    "en": {"day": "day {n}", "month": "month {n}",
           "missed": "Missed: {what} visit (was due {due}). The series is incomplete; ask your ANM.",
           "overdue": "Late: {what} visit (due {due}). Visit as soon as you can.",
           "next": "Next: {what} visit on {due}.",
           "check": "Before claiming, confirm: {items}.",
           "failed": "Not payable: {items}.",
           "safe_d42": "mother and baby safe at day 42", "birth_registered": "birth registered",
           "not_safe_d42": "mother or baby not safe at day 42", "not_birth_registered": "birth not registered"},
    "hi": {"day": "दिन {n}", "month": "माह {n}",
           "missed": "छूटा: {what} का भ्रमण (देय था {due})। श्रृंखला अधूरी है; ANM से पूछें।",
           "overdue": "देर: {what} का भ्रमण (देय {due})। जल्दी भ्रमण करें।",
           "next": "अगला: {what} का भ्रमण, {due} को।",
           "check": "दावे से पहले पुष्टि करें: {items}।",
           "failed": "भुगतान योग्य नहीं: {items}।",
           "safe_d42": "42वें दिन माँ और शिशु सुरक्षित", "birth_registered": "जन्म पंजीकृत",
           "not_safe_d42": "42वें दिन माँ या शिशु सुरक्षित नहीं", "not_birth_registered": "जन्म पंजीकृत नहीं"},
}
MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def load_template() -> dict:
    return load_yaml(TEMPLATE_PATH)


def _in_month(d: date | None, year: int, month: int) -> bool:
    return d is not None and (d.year, d.month) == (year, month)


def _label(p: Person, lang: str) -> str:
    return (p.label_hi if lang == "hi" else p.label_en) or p.label_en or p.id


def _date(d: date, lang: str) -> str:
    return f"{d.day}/{d.month}" if lang == "hi" else f"{d.day} {MONTHS_EN[d.month - 1]}"


def _what(t: engine.Task, lang: str) -> str:
    if t.programme == "HBNC":
        return TEXT[lang]["day"].format(n=t.rule_id.removeprefix("hbnc_d"))
    return TEXT[lang]["month"].format(n=t.rule_id.removeprefix("hbyc_m"))


def _todo(tasks: list[engine.Task], lang: str) -> list[str]:
    """What she can still do about a running series: missed/late visits first, then the next visit."""
    s, out = TEXT[lang], []
    for t in sorted(tasks, key=lambda t: t.due_date):
        if t.status in OVERDUE:
            out.append(s[t.status].format(what=_what(t, lang), due=_date(t.due_date, lang)))
    nxt = min((t for t in tasks if t.status not in ("done", *OVERDUE)), key=lambda t: t.due_date, default=None)
    if nxt is not None:
        out.append(s["next"].format(what=_what(nxt, lang), due=_date(nxt.due_date, lang)))
    return out


def claim_sheet(people: list[Person], inputs, today: date, year: int, month: int, lang: str,
                template: dict | None = None) -> dict:
    tpl = template or load_template()
    rates = tpl["rates"]
    s = TEXT[lang]
    # Always the 2014/2018 schedules: the claim sheet follows the national HBNC/HBYC incentive rules, and SSBSK
    # incentive amounts are not published yet [S36 p. 60] (D-32).
    tasks = engine.compute_tasks(inputs.beneficiaries, inputs.visits, inputs.doses, today, engine.load_ruleset())
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
                checks = {k: getattr(p, k, None) for k in CHECKS}
                failed = [k for k in CHECKS if checks[k] is False]
                unknown = [k for k in CHECKS if checks[k] is None]
                if failed:
                    status, todo = "not_eligible", [s["failed"].format(items="; ".join(s["not_" + k] for k in failed))]
                elif unknown:
                    status, todo = "check_conditions", [s["check"].format(items="; ".join(s[k] for k in unknown))]
                else:
                    status, todo = "ready", []
                rows.append(_row("HBNC", p, lang, f"{len(done)}/{len(hbnc)}", dates, status,
                                 rates["hbnc_series"] if status == "ready" else 0, todo,
                                 is_seeded(bid, "HBNC", dates), checks=checks,
                                 pending=rates["hbnc_series"] if status == "check_conditions" else 0))
        elif hbnc and (any(_in_month(t.done_on, year, month) for t in done)
                       or any(_in_month(t.due_date, year, month) for t in hbnc)):
            status = "missing_visit" if any(t.status in OVERDUE for t in hbnc) else "in_progress"
            rows.append(_row("HBNC", p, lang, f"{len(done)}/{len(hbnc)}", dates, status, 0, _todo(hbnc, lang),
                             is_seeded(bid, "HBNC", dates)))
        for t in tasks:
            if t.beneficiary_id != bid or t.programme != "HBYC":
                continue
            month_no = t.rule_id.removeprefix("hbyc_m")
            if t.status == "done" and _in_month(t.done_on, year, month):
                rows.append(_row("HBYC", p, lang, month_no, [t.done_on], "ready", rates["hbyc_visit"], [],
                                 is_seeded(bid, "HBYC", [t.done_on])))
            elif t.status != "done" and _in_month(t.due_date, year, month):
                rows.append(_row("HBYC", p, lang, month_no, [],
                                 "missing_visit" if t.status in OVERDUE else "in_progress", 0, _todo([t], lang), False))

    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], r["programme"], r["label"]))
    return {"month": f"{year:04d}-{month:02d}", "rows": rows, "total": sum(r["amount"] for r in rows),
            "pending": sum(r["pending"] for r in rows),
            "warning": tpl["warning"][lang], "not_computed": tpl["not_computed"][lang],
            "status": tpl["status"], "generated_on": today.isoformat()}


def _row(programme: str, p: Person, lang: str, detail: str, dates: list[date], status: str, amount: int,
         todo: list[str], seeded: bool, checks: dict | None = None, pending: int = 0) -> dict:
    """`todo`: what she can do next (plain sentences in her language); `conditions` joins them for the
    PDF/Excel column. `checks`: the HBNC payment conditions as she confirmed them (None = not yet)."""
    return {"programme": programme, "beneficiary_id": p.id, "label": _label(p, lang), "detail": detail,
            "dates": [d.isoformat() for d in dates], "status": status, "amount": amount, "pending": pending,
            "todo": todo, "conditions": " ".join(todo), "checks": checks, "seeded": seeded}
