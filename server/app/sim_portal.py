"""SIMULATED practice portal: government-style data-entry pages built from rules/forms/*.yaml, so the
A.U.R.A. autofill service can be shown filling a web form in Chrome. Not a government website, no government
names or logos; it stores nothing and sends nothing ("Submit" only clears the page). Field names are
deliberately not A.U.R.A.'s ids: autofill has to find fields by their labels, as on a real portal."""

from __future__ import annotations

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from .extraction.details import catalog as detail_catalog
from .forms import FORM_IDS, PERSON_DETAIL, load_form

router = APIRouter(prefix="/sim-portal")

STYLE = """
body{font-family:system-ui,sans-serif;margin:0;background:#eef1f4;color:#1b1f23}
header{background:#3b4a5a;color:#fff;padding:12px 16px}
header b{display:block;font-size:18px}
.sim{background:#ffe9a8;color:#5e3f00;padding:10px 16px;font-weight:600}
main{max-width:640px;margin:0 auto;padding:12px 16px 40px}
fieldset{background:#fff;border:1px solid #c9d1d9;border-radius:6px;margin:12px 0;padding:8px 12px}
legend{font-weight:700;padding:0 4px}
.row{display:flex;flex-direction:column;margin:10px 0}
label{font-size:14px;margin-bottom:4px}
input,select{font-size:16px;padding:8px;border:1px solid #9aa5b1;border-radius:4px;background:#fff}
button{font-size:16px;padding:10px 18px;margin-top:8px;background:#3b4a5a;color:#fff;border:0;border-radius:4px}
a{color:#1d4f91}
"""


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} — SIMULATED</title>
<style>{STYLE}</style></head><body>
<header><b>Practice data-entry portal</b>SIMULATED · for the A.U.R.A. autofill demo</header>
<div class="sim">SIMULATED — not a government website. Nothing you type here is saved or sent.</div>
<main>{body}</main></body></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


@router.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    links = "".join(f'<li><a href="/sim-portal/{fid}">{escape(load_form(fid)["title"]["en"])}</a></li>'
                    for fid in FORM_IDS)
    return _page("Forms", f"<h1>Choose a form</h1><ul>{links}</ul>")


def _field(n: int, item: dict) -> str:
    fid = f"fld{n}"
    text = f'{item["en"]} / {item["hi"]}'
    kind = item["kind"]
    did = item.get("detail") if kind == "detail" else item.get("field") if item.get("field") in PERSON_DETAIL else None
    dtype = detail_catalog()[did]["type"] if did else None
    if dtype == "choice":
        opts = "".join(f"<option>{escape(o['en'])}</option>" for o in detail_catalog()[did]["options"].values())
        ctrl = f'<select id="{fid}" name="{fid}"><option value="">-- Select --</option>{opts}</select>'
    elif dtype == "yesno":
        kind = "sign"
    elif dtype == "number":
        kind = "number"
    if dtype == "choice":
        pass
    elif kind in ("sign", "vaccine", "service", "referral"):
        ctrl = (f'<select id="{fid}" name="{fid}"><option value="">-- Select --</option>'
                '<option>Yes</option><option>No</option></select>')
    elif kind in ("date", "dose_date") or (kind == "person" and item.get("field") == "dob"):
        ctrl = f'<input id="{fid}" name="{fid}" type="text" placeholder="dd-mm-yyyy" autocomplete="off">'
    elif kind in ("number", "temp_f", "day", "month"):
        ctrl = f'<input id="{fid}" name="{fid}" type="text" inputmode="decimal" autocomplete="off">'
    else:
        ctrl = f'<input id="{fid}" name="{fid}" type="text" autocomplete="off">'
    return f'<div class="row"><label for="{fid}">{escape(text)}</label>{ctrl}</div>'


@router.get("/{form_id}", response_class=HTMLResponse)
def form_page(form_id: str) -> HTMLResponse:
    form = load_form(form_id)
    if form is None:
        return _page("Not found", '<p>No such form. <a href="/sim-portal/">All forms</a></p>')
    n = 0
    parts = ['<fieldset><legend>Login (practice)</legend>'
             '<div class="row"><label for="uid">User ID</label><input id="uid" name="uid" type="text" autocomplete="off"></div>'
             '<div class="row"><label for="pwd">Password</label><input id="pwd" name="pwd" type="password"></div>'
             '<p style="font-size:13px">A.U.R.A. never reads or fills login, password or OTP fields.</p></fieldset>']
    for sec in form["sections"]:
        rows = []
        for item in sec["items"]:
            n += 1
            rows.append(_field(n, item))
        parts.append(f'<fieldset><legend>{escape(sec["title"]["en"])} / {escape(sec["title"]["hi"])}</legend>{"".join(rows)}</fieldset>')
    body = (f'<h1>{escape(form["title"]["en"])}</h1><p><a href="/sim-portal/">All forms</a></p>'
            f'<form id="f" autocomplete="on">{"".join(parts)}<button type="submit">Submit (practice)</button></form>'
            '<script>document.getElementById("f").addEventListener("submit",function(e){e.preventDefault();'
            'alert("SIMULATED: nothing was sent.");this.reset();});</script>')
    return _page(form["title"]["en"], body)
