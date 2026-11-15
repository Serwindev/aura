"""Privacy audit (T-060, goal G5): checks the code against the privacy contract and writes a report.

Contract (CLAUDE.md): no location, contacts, call log, SMS, other-app monitoring, attendance or
productivity scoring; permissions = microphone (+ notifications later); no transcripts in logs;
outside services only where disclosed. This is a static scan of our own code, not a penetration
test: it proves what the code *asks for and calls*, and is re-run by the test suite.

    python scripts/privacy_audit.py [--out docs/privacy-audit.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "server" / "app" / "web"
SERVER = ROOT / "server" / "app"

# Browser APIs the contract forbids (or that would need a new decision first)
FORBIDDEN_WEB = {
    "location (GPS)": r"navigator\.geolocation|getCurrentPosition|watchPosition",
    "contacts": r"navigator\.contacts|ContactsManager",
    "camera / screen capture": r"video\s*:\s*true|getDisplayMedia",
    "SMS / OTP auto-read": r"navigator\.credentials\.get\([^)]*otp|WebOTP",
    "Bluetooth / USB / NFC / serial": r"navigator\.(bluetooth|usb|nfc|serial|hid)\b|NDEFReader",
    "motion / orientation sensors": r"DeviceMotionEvent|DeviceOrientationEvent|Accelerometer|Gyroscope",
    "background tracking beacons": r"navigator\.sendBeacon",
    "clipboard reading": r"clipboard\.read",
    "third-party scripts or fonts": r"<script[^>]+src=[\"']https?://|@import\s+url\(\s*[\"']?https?://|fonts\.googleapis",
}
ALLOWED_WEB_APIS = {
    "microphone": r"getUserMedia\(\s*\{\s*audio",
    "IndexedDB (unsent notes, this phone only)": r"indexedDB\.open",
    "localStorage (login token, language, last task list)": r"localStorage\.",
    "service worker (app shell, no API data)": r"serviceWorker\.register",
    "speech synthesis (read aloud; on-device voices only)": r"localService",
}
# Outside hosts the server may call, and where each is disclosed
ALLOWED_HOSTS = {
    "api.sarvam.ai": "speech-to-text when SARVAM_API_KEY is set; disclosed in Settings > Privacy (stt_cloud)",
    "alphacephei.com": "one-time Vosk model download by `make models` (developer machine, not at runtime)",
}
SDK_SERVICES = {  # outside services reached through an SDK rather than a URL in our code
    "Anthropic API (Claude)": (r"import anthropic", "note text only, when LLM_PROVIDER=anthropic; disclosed in Settings > Privacy (llm_cloud)"),
}
SCORING = r"\b(productivity|attendance|performance_score|leaderboard|ranking|time_on_task|track_location)\b"
LOG_CALL = re.compile(r"\blog(?:ger)?\.(debug|info|warning|error|exception)\((.*)\)")


def rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def scan() -> dict:
    web_files = sorted(p for p in WEB.rglob("*") if p.suffix in (".js", ".html", ".css"))
    py_files = sorted(p for p in SERVER.rglob("*.py"))
    findings: list[str] = []
    rows: list[tuple[str, str, str]] = []

    web_text = {p: read(p) for p in web_files}
    for what, rx in FORBIDDEN_WEB.items():
        hits = [f"{rel(p)}" for p, s in web_text.items() if re.search(rx, s)]
        rows.append((f"Web app does not use {what}", "PASS" if not hits else "FAIL", ", ".join(hits) or "no matches"))
        if hits:
            findings.append(f"forbidden browser API ({what}) in {hits}")
    for what, rx in ALLOWED_WEB_APIS.items():
        hits = [rel(p) for p, s in web_text.items() if re.search(rx, s)]
        rows.append((f"Uses {what}", "INFO", ", ".join(hits) or "not used"))

    # Permissions-Policy header: microphone only
    main = read(SERVER / "main.py")
    pp = re.search(r'Permissions-Policy"\]\s*=\s*"([^"]+)"', main)
    policy = pp.group(1) if pp else ""
    ok = "microphone=(self)" in policy and "geolocation=()" in policy and "camera=()" in policy
    rows.append(("Permissions-Policy header allows microphone only", "PASS" if ok else "FAIL", policy or "missing"))
    if not ok:
        findings.append("Permissions-Policy header does not restrict to microphone")

    # Outgoing hosts in server code (+ scripts that run on the developer machine)
    hosts: dict[str, set[str]] = {}
    for p in [*py_files, ROOT / "make.ps1", ROOT / "Makefile"]:
        if not p.exists():
            continue
        for h in re.findall(r"https?://([a-zA-Z0-9.-]+)", read(p)):
            if h in ("localhost", "127.0.0.1", "0.0.0.0") or h.endswith(".example.com"):
                continue
            hosts.setdefault(h, set()).add(rel(p))
    for h, where in sorted(hosts.items()):
        if h in ALLOWED_HOSTS:
            rows.append((f"Outside host {h}", "PASS", ALLOWED_HOSTS[h]))
        else:
            rows.append((f"Outside host {h}", "FAIL", "not on the allow-list: " + ", ".join(sorted(where))))
            findings.append(f"undeclared outside host {h} in {sorted(where)}")
    py_text = {p: read(p) for p in py_files}
    for svc, (rx, note) in SDK_SERVICES.items():
        used = [rel(p) for p, s in py_text.items() if re.search(rx, s)]
        rows.append((f"Outside service {svc}", "PASS" if used else "INFO", note if used else "not used"))
    web_hosts = sorted({h for s in web_text.values() for h in re.findall(r"https?://([a-zA-Z0-9.-]+)", s)
                        if h not in ("www.w3.org",)})
    rows.append(("Phone talks only to our own server", "PASS" if not web_hosts else "FAIL",
                 "no outside URLs in the web app" if not web_hosts else ", ".join(web_hosts)))
    if web_hosts:
        findings.append(f"web app references outside hosts {web_hosts}")

    # No scoring / attendance / tracking concepts anywhere in server or web code
    def scoring_lines(s: str) -> bool:  # lines that promise we *never* collect these are disclosures, not use
        return any(re.search(SCORING, ln, re.I) and not re.search(r"never|नहीं|कभी", ln, re.I) for ln in s.splitlines())

    score_hits = sorted({rel(p) for p, s in {**web_text, **py_text}.items()
                         if p.name != "privacy_audit.py" and scoring_lines(s)})
    rows.append(("No attendance, productivity or location scoring", "PASS" if not score_hits else "FAIL",
                 ", ".join(score_hits) or "no matches"))
    if score_hits:
        findings.append(f"scoring/tracking terms in {score_hits}")

    # Logs never carry transcripts or note text
    leaks = []
    for p, s in py_text.items():
        for m in LOG_CALL.finditer(s):
            if re.search(r"transcript|\.text\b|note\.draft|confirmed|phone", m.group(2)):
                leaks.append(f"{rel(p)}: {m.group(0)[:80]}")
    prints = [rel(p) for p, s in py_text.items() if re.search(r"^\s*print\(", s, re.M)]
    rows.append(("Logs never include transcripts, note text or phone numbers", "PASS" if not leaks else "FAIL",
                 "; ".join(leaks) or "no log call references them"))
    rows.append(("No print() in server code", "PASS" if not prints else "FAIL", ", ".join(prints) or "none"))
    findings += [f"log leak: {x}" for x in leaks] + [f"print() in {x}" for x in prints]

    # Audio retention and the on-phone queue
    settings = read(SERVER / "core" / "settings.py")
    services = read(SERVER / "services.py")
    ret = "audio_retention_hours: int = 168" in settings and "def purge_expired_audio" in services
    rows.append(("Server audio deleted on confirm/discard, 7-day cap (D-07)", "PASS" if ret else "FAIL",
                 "AUDIO_RETENTION_HOURS default 168; purge_expired_audio()"))
    if not ret:
        findings.append("audio retention rule missing")
    clears = "Outbox.clear" in web_text.get(WEB / "app.js", "")
    rows.append(("'Delete my data' also clears unsent notes on the phone (D-28)", "PASS" if clears else "FAIL",
                 "app.js calls Outbox.clear()" if clears else "missing"))
    if not clears:
        findings.append("delete-my-data does not clear the phone outbox")
    return {"rows": rows, "findings": findings, "files": len(web_files) + len(py_files)}


def render(res: dict) -> str:
    out = [f"# Privacy audit — {date.today().isoformat()} — **{'PASS' if not res['findings'] else 'FAIL'}**", "",
           "> Static scan of our own code against the privacy contract (`CLAUDE.md`). It shows what the app",
           "> asks for and which outside services it calls; it is not a penetration test and does not cover",
           "> the phone's OS, the browser, or the vendors' own handling (Sarvam/Anthropic retention are vendor claims).",
           f"> Generated by `python scripts/privacy_audit.py` over {res['files']} files; re-run by the test suite.", "",
           "| Check | Result | Detail |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c.replace('|', '/')} |" for a, b, c in res["rows"]]
    out += ["", "## Data flows", "",
            "| Data | Where it goes | When deleted |", "|---|---|---|",
            "| Voice recording | phone → our server (laptop); server → Sarvam (India) for speech-to-text if a key is set | on confirm or discard; 7-day cap |",
            "| Note text (transcript) | our server; → Anthropic only if `LLM_PROVIDER=anthropic` | with the note (Delete my data) |",
            "| Unsent note (audio/text) | this phone only (IndexedDB) until sent | when sent, deleted by her, or Delete my data |",
            "| Login token, language, last task list | this phone (localStorage) | logout (token) / Delete my data (task list) |",
            "| Phone number, name, ASHA ID | our server | Delete my data removes notes; account row stays for login |",
            "", "Only synthetic data is used in this prototype."]
    if res["findings"]:
        out += ["", "## Findings", "", *[f"- {f}" for f in res["findings"]]]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "privacy-audit.md"))
    args = ap.parse_args()
    res = scan()
    Path(args.out).write_text(render(res), encoding="utf-8", newline="\n")
    print(f"privacy audit: {'PASS' if not res['findings'] else 'FAIL'} ({len(res['rows'])} checks) -> {args.out}")
    for f in res["findings"]:
        print("  -", f)
    sys.exit(1 if res["findings"] else 0)


if __name__ == "__main__":
    main()
