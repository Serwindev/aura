"""Monthly report (T-055b): every confirmed visit in the month, a summary, open tasks and the
incentive claim support sheet, as one Excel workbook or one PDF.

Built only from records the ASHA confirmed. Demo history is labelled SIMULATED. Incentive figures
come from claims.claim_sheet (advisory estimate at configured rates; never a filed claim).
"""

from __future__ import annotations

import io
from collections import Counter
from datetime import date

from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import RULES_DIR, load_yaml
from ..db.models import Note
from ..rules import engine
from .export import FONT, LATIN_FONT
from .export import STRINGS as CLAIM_STRINGS

VISIT_LABELS = {
    "HBNC": ("HBNC (newborn home visit)", "HBNC (नवजात गृह भ्रमण)"),
    "HBYC": ("HBYC (young child home visit)", "HBYC (शिशु गृह भ्रमण)"),
    "ANC": ("ANC (pregnancy check)", "ANC (गर्भावस्था जाँच)"),
    "PNC": ("PNC (after delivery)", "PNC (प्रसव के बाद)"),
    "IMMUNIZATION": ("Immunisation", "टीकाकरण"),
    "FAMILY_PLANNING": ("Family planning", "परिवार नियोजन"),
    "TB_FOLLOWUP": ("TB follow-up", "टीबी फॉलो-अप"),
    "NCD_FOLLOWUP": ("NCD follow-up", "एनसीडी फॉलो-अप"),
    "OTHER": ("Other", "अन्य"),
}
SERVICE_LABELS = {"IFA": ("Iron-folic acid", "आयरन-फोलिक"), "CALCIUM": ("Calcium", "कैल्शियम"),
                  "ORS": ("ORS", "ओआरएस"), "ZINC": ("Zinc", "जिंक"), "COUNSELLING": ("Counselling", "परामर्श")}

S = {
    "en": {"title": "Monthly activity report", "month": "Month", "asha": "ASHA", "id": "ASHA ID",
           "generated": "Generated", "synthetic": "Demo — synthetic data only",
           "advisory": "Prepared from visit notes the ASHA confirmed. Advisory; verification stays with the ANM.",
           "summary": "Summary", "visits_total": "Visits recorded", "by_type": "Visits by type",
           "vaccines": "Vaccine doses recorded", "danger": "Visits with danger signs",
           "referrals": "Referrals", "people": "People visited", "overdue": "Overdue / missed tasks",
           "due_soon": "Tasks due in the next 7 days", "incentive": "Estimated incentive (₹)",
           "visits": "Visit records", "date": "Date", "person": "Beneficiary", "type": "Visit type",
           "stage": "Day / month / no.", "weight": "Weight (kg)", "temp": "Temp (°C)", "bp": "BP",
           "hb": "Hb (g/dL)", "danger_signs": "Danger signs", "services": "Services / vaccines",
           "referral": "Referral", "source": "Entered by", "voice": "Voice", "typed": "Typed",
           "demo": "Demo history (SIMULATED)", "none": "No confirmed visits this month",
           "tasks": "Open tasks", "due": "Due", "status": "Status", "reason": "Why",
           "overdue_s": "Overdue", "missed": "Missed", "due_s": "Due", "upcoming": "Upcoming",
           "claims": "Incentive claim support", "yes": "Yes", "count": "Count",
           "ncomp": "Incentive covers HBNC and HBYC home visits only."},
    "hi": {"title": "मासिक गतिविधि रिपोर्ट", "month": "माह", "asha": "आशा", "id": "आशा आईडी",
           "generated": "बनाई गई", "synthetic": "डेमो — केवल काल्पनिक डेटा",
           "advisory": "आशा द्वारा पुष्टि किए गए भ्रमण नोट से बनी। केवल सलाह; सत्यापन ANM करेंगी।",
           "summary": "सारांश", "visits_total": "दर्ज भ्रमण", "by_type": "प्रकार अनुसार भ्रमण",
           "vaccines": "दर्ज टीके की खुराक", "danger": "खतरे के लक्षण वाले भ्रमण",
           "referrals": "रेफरल", "people": "लाभार्थी जिनसे मिले", "overdue": "छूटे / देर वाले काम",
           "due_soon": "अगले 7 दिन में देय काम", "incentive": "अनुमानित प्रोत्साहन राशि (₹)",
           "visits": "भ्रमण रिकॉर्ड", "date": "तारीख", "person": "लाभार्थी", "type": "भ्रमण प्रकार",
           "stage": "दिन / माह / क्रम", "weight": "वजन (किलो)", "temp": "तापमान (°C)", "bp": "बीपी",
           "hb": "एचबी (g/dL)", "danger_signs": "खतरे के लक्षण", "services": "सेवाएँ / टीके",
           "referral": "रेफरल", "source": "दर्ज करने का तरीका", "voice": "आवाज़", "typed": "टाइप",
           "demo": "डेमो इतिहास (SIMULATED)", "none": "इस माह कोई पुष्टि किया भ्रमण नहीं",
           "tasks": "बाकी काम", "due": "देय", "status": "स्थिति", "reason": "क्यों",
           "overdue_s": "देर", "missed": "छूटा", "due_s": "देय", "upcoming": "आगामी",
           "claims": "प्रोत्साहन दावा सहायक", "yes": "हाँ", "count": "संख्या",
           "ncomp": "प्रोत्साहन में केवल HBNC और HBYC गृह भ्रमण शामिल हैं।"},
}
TASK_STATUS = {"overdue": "overdue_s", "missed": "missed", "due": "due_s", "due_soon": "due_s", "upcoming": "upcoming"}


def _danger_labels() -> dict[str, tuple[str, str]]:
    raw = load_yaml(RULES_DIR / "validation.yaml")["danger_signs"]
    return {code: (v["en"], v["hi"]) for group in raw.values() for code, v in group.items()}


def _pick(pair: tuple[str, str], lang: str) -> str:
    return pair[1] if lang == "hi" else pair[0]


def _num(v) -> str:
    return "" if v is None else f"{v:g}"


def build(db: Session, owner_id: str, people: list, inputs, claim: dict, today: date, year: int,
          month: int, lang: str) -> dict:
    """Pure data for the report (also the JSON format)."""
    s = S[lang]
    by_id = {p.id: p for p in people}
    dangers = _danger_labels()
    visits: list[dict] = []
    notes = db.scalars(select(Note).where(Note.owner_id == owner_id, Note.status == "confirmed")).all()
    for n in notes:
        r = n.confirmed or {}
        when = date.fromisoformat(r["visit_date"]) if r.get("visit_date") else n.recorded_on
        if (when.year, when.month) != (year, month):
            continue
        bid = (r.get("beneficiary") or {}).get("matched_id")
        p = by_id.get(bid)
        idx, vit, ref = r.get("visit_index") or {}, r.get("vitals") or {}, r.get("referral") or {}
        stage = idx.get("hbnc_day") or idx.get("hbyc_month") or idx.get("anc_number")
        services = []
        for sv in r.get("services_given") or []:
            if sv.get("type") == "VACCINE":
                services.append(sv.get("detail") or "Vaccine")
            elif sv.get("type") in SERVICE_LABELS:
                services.append(_pick(SERVICE_LABELS[sv["type"]], lang))
            elif sv.get("detail"):
                services.append(sv["detail"])
        bp = f"{_num(vit.get('bp_sys'))}/{_num(vit.get('bp_dia'))}" if vit.get("bp_sys") else ""
        visits.append({
            "date": when.isoformat(),
            "beneficiary_id": bid or "",
            "person": ((p.label_hi if lang == "hi" else p.label_en) or p.label_en or p.id) if p else "-",
            "visit_type": r.get("visit_type") or "OTHER",
            "type_label": _pick(VISIT_LABELS.get(r.get("visit_type") or "OTHER", VISIT_LABELS["OTHER"]), lang),
            "stage": "" if stage is None else str(stage),
            "weight_kg": vit.get("weight_kg"), "temp_c": vit.get("temp_c"), "bp": bp, "hb_g_dl": vit.get("hb_g_dl"),
            "danger_signs": [_pick(dangers.get(d["code"], (d["code"], d["code"])), lang)
                             for d in r.get("danger_signs") or [] if d.get("present")],
            "vaccines": [sv.get("detail") or "Vaccine" for sv in r.get("services_given") or [] if sv.get("type") == "VACCINE"],
            "services": services,
            "referral": ((ref.get("facility") or s["yes"]) if ref.get("needed") else ""),
            "source": s["demo"] if n.source == "seed" else (s["voice"] if n.source == "audio" else s["typed"]),
            "simulated": n.source == "seed",
        })
    visits.sort(key=lambda v: (v["date"], v["person"]))

    tasks = engine.compute_tasks(inputs.beneficiaries, inputs.visits, inputs.doses, today, inputs.rules())
    soon = [t for t in tasks if t.status in ("due", "due_soon", "upcoming") and 0 <= (t.due_date - today).days <= 7]
    open_rows = [{"person": ((by_id[t.beneficiary_id].label_hi if lang == "hi" else by_id[t.beneficiary_id].label_en)
                             or t.beneficiary_id) if t.beneficiary_id in by_id else t.beneficiary_id,
                  "programme": t.programme, "due_date": t.due_date.isoformat(),
                  "status": s[TASK_STATUS[t.status]] if t.status in TASK_STATUS else t.status,
                  "reason": t.reason_hi if lang == "hi" else t.reason_en}
                 for t in sorted(tasks, key=lambda t: t.due_date)
                 if t.status in ("overdue", "missed") or any(t is x for x in soon)]

    by_type = Counter(v["type_label"] for v in visits)
    vaccines = Counter(x for v in visits for x in v["vaccines"])
    summary = [
        (s["visits_total"], len(visits)),
        (s["people"], len({v["beneficiary_id"] for v in visits if v["beneficiary_id"]})),
        (s["vaccines"], sum(vaccines.values())),
        (s["danger"], sum(1 for v in visits if v["danger_signs"])),
        (s["referrals"], sum(1 for v in visits if v["referral"])),
        (s["overdue"], sum(1 for t in tasks if t.status in ("overdue", "missed"))),
        (s["due_soon"], len(soon)),
        (s["incentive"], claim["total"]),
    ]
    return {"month": f"{year:04d}-{month:02d}", "generated_on": today.isoformat(), "lang": lang,
            "summary": [{"label": k, "value": v} for k, v in summary],
            "by_type": [{"label": k, "count": c} for k, c in sorted(by_type.items())],
            "vaccines": [{"label": k, "count": c} for k, c in sorted(vaccines.items())],
            "visits": visits, "tasks": open_rows, "claims": claim}


# ---- Excel ----------------------------------------------------------------------------------

_HEAD_FILL = PatternFill("solid", fgColor="E8EEE8")


def _heading_row(ws, values: list) -> None:
    ws.append(values)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
        c.fill = _HEAD_FILL


def _widths(ws, widths: tuple[int, ...]) -> None:
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(ord("A") + i)].width = w


def to_xlsx(rep: dict, user: dict) -> bytes:
    lang = rep["lang"]
    s, cs = S[lang], CLAIM_STRINGS[lang]
    wb = Workbook()

    ws = wb.active
    ws.title = "Summary"
    ws.append([s["title"]])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([s["month"], rep["month"], s["asha"], user.get("name") or "-", s["id"], user.get("asha_id") or "-"])
    ws.append([s["generated"], rep["generated_on"]])
    ws.append([f"{s['synthetic']}. {s['advisory']}"])
    ws["A4"].font = Font(color="A02814")
    ws.append([])
    _heading_row(ws, [s["summary"], s["count"]])
    for row in rep["summary"]:
        ws.append([row["label"], row["value"]])
    ws.append([])
    _heading_row(ws, [s["by_type"], s["count"]])
    for row in rep["by_type"]:
        ws.append([row["label"], row["count"]])
    ws.append([])
    _heading_row(ws, [s["vaccines"], s["count"]])
    for row in rep["vaccines"]:
        ws.append([row["label"], row["count"]])
    _widths(ws, (44, 14, 10, 22, 12, 16))

    wv = wb.create_sheet("Visits")
    _heading_row(wv, [s["date"], s["person"], s["type"], s["stage"], s["weight"], s["temp"], s["bp"], s["hb"],
                      s["danger_signs"], s["services"], s["referral"], s["source"]])
    for v in rep["visits"]:
        wv.append([v["date"], v["person"], v["type_label"], v["stage"], v["weight_kg"], v["temp_c"], v["bp"],
                   v["hb_g_dl"], ", ".join(v["danger_signs"]), ", ".join(v["services"]), v["referral"], v["source"]])
    if not rep["visits"]:
        wv.append([s["none"]])
    wv.freeze_panes = "A2"
    wv.auto_filter.ref = wv.dimensions
    _widths(wv, (12, 22, 26, 10, 11, 10, 9, 10, 32, 32, 16, 22))

    wt = wb.create_sheet("Tasks")
    _heading_row(wt, [s["person"], s["type"], s["due"], s["status"], s["reason"]])
    for t in rep["tasks"]:
        wt.append([t["person"], t["programme"], t["due_date"], t["status"], t["reason"]])
    _widths(wt, (22, 10, 12, 12, 70))

    claim = rep["claims"]
    wc = wb.create_sheet("Incentive")
    wc.append([cs["title"]])
    wc["A1"].font = Font(bold=True, size=13)
    wc.append([claim["warning"]])
    wc["A2"].font = Font(color="A02814")
    _heading_row(wc, [cs["programme"], cs["person"], cs["detail"], cs["dates"], cs["status"], cs["amount"],
                      cs["conditions"], "SIMULATED"])
    first = wc.max_row + 1
    for r in claim["rows"]:
        wc.append([r["programme"], r["label"], r["detail"], ", ".join(r["dates"]), cs[r["status"]], r["amount"],
                   r["conditions"], "SIMULATED" if r["seeded"] else ""])
    last = wc.max_row
    wc.append([])
    wc.append([cs["total"], None, None, None, None, f"=SUM(F{first}:F{last})" if last >= first else 0])
    wc.cell(wc.max_row, 1).font = Font(bold=True)
    wc.append([claim["not_computed"]])
    _widths(wc, (12, 30, 8, 34, 14, 12, 52, 12))
    for row in wc.iter_rows(min_row=first, max_row=last, min_col=7, max_col=7):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---- PDF ------------------------------------------------------------------------------------

def _pdf() -> FPDF:
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_margin(12)
    pdf.set_auto_page_break(True, 12)
    pdf.add_font("Noto", "", str(FONT))
    pdf.add_font("Latin", "", str(LATIN_FONT))
    pdf.set_fallback_fonts(["Latin"])
    pdf.set_text_shaping(True)
    return pdf


def _h2(pdf: FPDF, text: str) -> None:
    if pdf.get_y() > pdf.h - 60:  # never leave a heading alone at the foot of a page
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font("Noto", "", 13)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 9)


_HEAD = FontFace(emphasis=None, fill_color=(232, 238, 232))


def to_pdf(rep: dict, user: dict) -> bytes:
    lang = rep["lang"]
    s, cs = S[lang], CLAIM_STRINGS[lang]
    pdf = _pdf()
    pdf.add_page()
    pdf.set_font("Noto", "", 17)
    pdf.cell(0, 10, s["title"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 10)
    pdf.cell(0, 7, f"{s['month']}: {rep['month']}   {s['asha']}: {user.get('name') or '-'}   "
                   f"{s['id']}: {user.get('asha_id') or '-'}   {s['generated']}: {rep['generated_on']}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(160, 40, 20)
    pdf.multi_cell(0, 6, f"{s['synthetic']}. {s['advisory']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    _h2(pdf, s["summary"])
    with pdf.table(col_widths=(90, 30), width=120, align="LEFT", headings_style=_HEAD, line_height=6,
                   text_align=("LEFT", "RIGHT")) as t:
        t.row((s["summary"], s["count"]))
        for row in rep["summary"]:
            t.row((row["label"], str(row["value"])))
    if rep["by_type"] or rep["vaccines"]:
        _h2(pdf, f"{s['by_type']} · {s['vaccines']}")
        pairs = [(r["label"], str(r["count"])) for r in rep["by_type"]]
        vac = [(r["label"], str(r["count"])) for r in rep["vaccines"]]
        rows = max(len(pairs), len(vac))
        pairs += [("", "")] * (rows - len(pairs))
        vac += [("", "")] * (rows - len(vac))
        with pdf.table(col_widths=(80, 20, 60, 20), width=180, align="LEFT", headings_style=_HEAD, line_height=6) as t:
            t.row((s["by_type"], s["count"], s["vaccines"], s["count"]))
            for a, b in zip(pairs, vac, strict=True):
                t.row((*a, *b))

    _h2(pdf, s["visits"])
    if rep["visits"]:
        with pdf.table(col_widths=(19, 30, 34, 13, 13, 13, 15, 12, 40, 40, 22, 22), headings_style=_HEAD,
                       line_height=5.5, text_align="LEFT") as t:
            t.row((s["date"], s["person"], s["type"], s["stage"], s["weight"], s["temp"], s["bp"], s["hb"],
                   s["danger_signs"], s["services"], s["referral"], s["source"]))
            for v in rep["visits"]:
                t.row((v["date"], v["person"], v["type_label"], v["stage"], _num(v["weight_kg"]), _num(v["temp_c"]),
                       v["bp"], _num(v["hb_g_dl"]), ", ".join(v["danger_signs"]), ", ".join(v["services"]),
                       v["referral"], v["source"]))
    else:
        pdf.cell(0, 7, s["none"], new_x="LMARGIN", new_y="NEXT")

    if rep["tasks"]:
        _h2(pdf, s["tasks"])
        with pdf.table(col_widths=(40, 20, 22, 22, 169), headings_style=_HEAD, line_height=5.5, text_align="LEFT") as t:
            t.row((s["person"], s["type"], s["due"], s["status"], s["reason"]))
            for r in rep["tasks"]:
                t.row((r["person"], r["programme"], r["due_date"], r["status"], r["reason"]))

    claim = rep["claims"]
    _h2(pdf, s["claims"])
    pdf.set_text_color(160, 40, 20)
    pdf.multi_cell(0, 5, claim["warning"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    if claim["rows"]:
        with pdf.table(col_widths=(18, 42, 14, 62, 24, 16, 97), headings_style=_HEAD, line_height=5.5,
                       text_align="LEFT") as t:
            t.row((cs["programme"], cs["person"], cs["detail"], cs["dates"], cs["status"], cs["amount"], cs["conditions"]))
            for r in claim["rows"]:
                name = f"{r['label']} — {cs['demo']}" if r["seeded"] else r["label"]
                t.row((r["programme"], name, r["detail"], ", ".join(d[8:10] + "/" + d[5:7] for d in r["dates"]),
                       cs[r["status"]], str(r["amount"]), r["conditions"]))
    else:
        pdf.cell(0, 7, cs["none"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 12)
    pdf.cell(0, 8, f"{cs['total']}: {claim['total']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 9)
    pdf.multi_cell(0, 5, f"{s['ncomp']} {claim['not_computed']}", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
