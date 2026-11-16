"""PDF (Hindi font embedded and shaped) and XLSX exports of the claim support sheet (T-055)."""

from __future__ import annotations

import io
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

FONT = Path(__file__).parent / "fonts" / "NotoSansDevanagari-Regular.ttf"
LATIN_FONT = Path(__file__).parent / "fonts" / "NotoSans-Regular.ttf"

STRINGS = {
    "hi": {"title": "प्रोत्साहन राशि दावा सहायक पत्रक", "month": "माह", "asha": "आशा", "id": "आशा आईडी",
           "programme": "कार्यक्रम", "person": "लाभार्थी", "detail": "भ्रमण", "dates": "तारीखें", "status": "स्थिति",
           "amount": "राशि (₹)", "conditions": "क्या करें", "total": "कुल अनुमान (₹)", "demo": "डेमो इतिहास (SIMULATED)",
           "synthetic": "डेमो — केवल काल्पनिक डेटा", "none": "इस माह के लिए कुछ नहीं",
           "ready": "तैयार", "missing_visit": "भ्रमण छूटा", "in_progress": "जारी",
           "check_conditions": "शर्तें जाँचें", "not_eligible": "भुगतान योग्य नहीं"},
    "en": {"title": "Incentive claim support sheet", "month": "Month", "asha": "ASHA", "id": "ASHA ID",
           "programme": "Programme", "person": "Beneficiary", "detail": "Visits", "dates": "Dates", "status": "Status",
           "amount": "Amount (₹)", "conditions": "What to do", "total": "Estimated total (₹)", "demo": "Demo history (SIMULATED)",
           "synthetic": "Demo — synthetic data only", "none": "Nothing for this month",
           "ready": "Ready", "missing_visit": "Missing visit", "in_progress": "In progress",
           "check_conditions": "Check conditions", "not_eligible": "Not payable"},
}


def _short_dates(dates: list[str]) -> str:
    return ", ".join(f"{d[8:10]}/{d[5:7]}" for d in dates)


def to_pdf(sheet: dict, user: dict, lang: str) -> bytes:
    s = STRINGS[lang]
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_margin(12)
    pdf.add_font("Noto", "", str(FONT))
    pdf.add_font("Latin", "", str(LATIN_FONT))  # the Devanagari font has no Latin letters
    pdf.set_fallback_fonts(["Latin"])
    pdf.set_text_shaping(True)
    pdf.add_page()
    pdf.set_font("Noto", "", 17)
    pdf.cell(0, 10, s["title"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 10)
    who = f"{s['month']}: {sheet['month']}   {s['asha']}: {user.get('name') or '-'}   {s['id']}: {user.get('asha_id') or '-'}"
    pdf.cell(0, 7, who, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(160, 40, 20)
    pdf.multi_cell(0, 6, f"{s['synthetic']}. {sheet['warning']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    if sheet["rows"]:
        heads = (s["programme"], s["person"], s["detail"], s["dates"], s["status"], s["amount"], s["conditions"])
        with pdf.table(col_widths=(18, 42, 14, 62, 24, 16, 74), headings_style=FontFace(emphasis=None, fill_color=(232, 238, 232)),
                       line_height=6.5, text_align="LEFT") as table:
            table.row(heads)
            for r in sheet["rows"]:
                name = f"{r['label']} — {s['demo']}" if r["seeded"] else r["label"]
                table.row((r["programme"], name, r["detail"], _short_dates(r["dates"]), s[r["status"]], str(r["amount"]), r["conditions"]))
    else:
        pdf.cell(0, 8, s["none"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Noto", "", 13)
    pdf.cell(0, 8, f"{s['total']}: {sheet['total']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Noto", "", 9)
    pdf.multi_cell(0, 5, sheet["not_computed"], new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def to_xlsx(sheet: dict, user: dict, lang: str) -> bytes:
    s = STRINGS[lang]
    wb = Workbook()
    ws = wb.active
    ws.title = "Claim support"
    ws.append([s["title"]])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([s["month"], sheet["month"], s["asha"], user.get("name") or "-", s["id"], user.get("asha_id") or "-"])
    ws.append([f"{s['synthetic']}. {sheet['warning']}"])
    ws["A3"].font = Font(color="A02814")
    ws.append([])
    heads = [s["programme"], s["person"], s["detail"], s["dates"], s["status"], s["amount"], s["conditions"], "SIMULATED"]
    ws.append(heads)
    for c in ws[5]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E8EEE8")
    first = ws.max_row + 1
    for r in sheet["rows"]:
        ws.append([r["programme"], r["label"], r["detail"], _short_dates(r["dates"]), s[r["status"]], r["amount"],
                   r["conditions"], "SIMULATED" if r["seeded"] else ""])
    last = ws.max_row
    ws.append([])
    ws.append([s["total"], None, None, None, None, f"=SUM(F{first}:F{last})" if last >= first else 0])
    ws.cell(ws.max_row, 1).font = Font(bold=True)
    ws.append([sheet["not_computed"]])
    for col, width in zip("ABCDEFGH", (12, 30, 8, 34, 14, 12, 52, 12), strict=True):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=first, max_row=last, min_col=7, max_col=7):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
