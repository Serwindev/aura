"""Offline soak test (T-061, goal G4): many offline -> online cycles in a real browser, then check that
every note reached the server exactly once. Synthetic notes only; mock speech-to-text (SIMULATED).

Runs the real server in-process (temp data dir) and headless Edge/Chrome over the DevTools protocol.
Each cycle: go offline, queue 1-3 notes (typed, every 4th a voice WAV), sometimes reload the page while
notes wait (every 10th cycle), go online, wait for the queue to empty. Every 25th cycle the server is
"down" (HTTP 503 on POST /v1/notes) instead of offline, to cover the server-error path too.

    python eval/offline_soak.py --cycles 200 --out eval/results/<date>/offline-soak
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import uvicorn  # noqa: E402
import websockets  # noqa: E402

from app.core.settings import load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.stt.providers import MockStt  # noqa: E402

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/microsoft-edge"]
VOICE_TEXT = "Visited Rekha baby, newborn visit, weight 3 kg, no fever."  # what the mock "hears"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Page:
    def __init__(self, ws):
        self.ws, self.n, self.errors = ws, 0, []

    async def call(self, method, **params):
        self.n += 1
        my = self.n
        await self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                self.errors.append(msg["params"]["exceptionDetails"].get("text", "exception"))
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    async def js(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:400])
        return r["result"].get("value")

    async def wait(self, expr, timeout=20.0):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if await self.js(expr):
                    return
            except RuntimeError:
                pass  # page mid-reload
            await asyncio.sleep(0.2)
        raise TimeoutError(expr)

    async def offline(self, on: bool):
        await self.call("Network.emulateNetworkConditions", offline=on, latency=0,
                        downloadThroughput=-1, uploadThroughput=-1)


SUBMIT_JS = """(async (text, voice) => {
  S.noteLang = 'en'; S.task = null;
  if (voice) {  // 1 s of quiet 16 kHz mono WAV: the mock speech-to-text returns a fixed sentence
    const n = 16000, buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    w(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, 16000, true);
    v.setUint32(28, 32000, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, n * 2, true);
    for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.round(Math.sin(i / 8) * 300), true);
    await submitNote({ wav: new Blob([buf], { type: 'audio/wav' }) });
  } else {
    await submitNote({ text });
  }
})"""


async def run(cycles: int, browser: str, base: str, server_down: dict) -> dict:
    port = free_port()
    prof = tempfile.mkdtemp()
    proc = subprocess.Popen([browser, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={prof}",
                             "--window-size=390,844", "--no-first-run", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stats = {"cycles": 0, "typed": 0, "voice": 0, "reloads": 0, "server_down_cycles": 0, "queued_seen": 0}
    sent_texts: list[str] = []
    try:
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.25)
        async with websockets.connect(ws_url, max_size=None) as ws:
            p = Page(ws)
            await p.call("Runtime.enable")
            await p.call("Network.enable")
            await p.call("Page.enable")
            await p.call("Page.navigate", url=base)
            await p.wait("!!document.querySelector('#f-phone')")
            await p.js("document.querySelector('[data-ui-lang=en]').click()")
            await p.wait("!!document.querySelector('#f-phone')")
            await p.js("const f=document.querySelector('#f-phone'); f.phone.value='9000011111'; f.requestSubmit()")
            await p.wait("!!document.querySelector('#f-otp')")
            await p.js("const o=document.querySelector('#f-otp'); o.otp.value=document.querySelector('#otp-area strong').textContent; o.requestSubmit()")
            await p.wait("!!S.user && S.view==='home'")
            t0 = time.time()
            for c in range(1, cycles + 1):
                down = c % 25 == 0
                if down:
                    server_down["on"] = True
                    stats["server_down_cycles"] += 1
                else:
                    await p.offline(True)
                k = 1 + (c % 3)
                for j in range(k):
                    voice = (c + j) % 4 == 0
                    text = f"Cycle {c} note {j + 1}: visited Sunita Devi baby today, weight 2.8 kg, no fever."
                    await p.js(f"{SUBMIT_JS}({json.dumps(text)}, {json.dumps(voice)})")
                    if voice:
                        stats["voice"] += 1
                    else:
                        stats["typed"] += 1
                        sent_texts.append(text)
                queued = await p.js("Outbox.list(owner()).then(l=>l.length)")
                stats["queued_seen"] = max(stats["queued_seen"], queued)
                if queued < k:
                    raise AssertionError(f"cycle {c}: expected >= {k} queued, found {queued}")
                if c % 10 == 0:  # reload while notes wait: they must survive in IndexedDB
                    await p.call("Page.reload")
                    await asyncio.sleep(0.5)
                    if down:
                        await p.wait("!!S.user")
                    else:
                        await p.wait("!!S.user && S.view==='home'")
                    stats["reloads"] += 1
                    left = await p.js("Outbox.list(owner()).then(l=>l.length)")
                    if left < k:
                        raise AssertionError(f"cycle {c}: notes lost on reload ({left} < {k})")
                server_down["on"] = False
                await p.offline(False)
                await p.js("window.dispatchEvent(new Event('online'))")
                await p.wait("Outbox.list(owner()).then(l=>l.length===0)", timeout=30)
                stats["cycles"] = c
                if c % 20 == 0:
                    print(f"  cycle {c}/{cycles} ok ({time.time() - t0:.0f} s)", flush=True)
            failed = await p.js("Outbox.list().then(l=>l.filter(x=>x.status==='failed').length)")
            stats["seconds"] = round(time.time() - t0, 1)
            stats["console_exceptions"] = p.errors
            stats["outbox_failed"] = failed
            return {"stats": stats, "sent_texts": sent_texts}
    finally:
        proc.kill()
        shutil.rmtree(prof, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=200)
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / date.today().isoformat() / "offline-soak"))
    args = ap.parse_args()
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("No Edge/Chrome found")

    data = Path(tempfile.mkdtemp())
    os.environ.pop("LLM_PROVIDER", None)  # rule-based extractor: no network, no cost
    cfg = load_settings(data)
    app = create_app(cfg, stt=MockStt(VOICE_TEXT), warm_stt=False)
    server_down = {"on": False, "real_5xx": 0}

    @app.middleware("http")
    async def maybe_down(request, call_next):  # simulated outage: the queue must keep the note
        if server_down["on"] and request.method == "POST" and request.url.path == "/v1/notes":
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": {"code": "DOWN", "message": "simulated outage", "details": []}}, 503)
        try:
            response = await call_next(request)
        except Exception:
            server_down["real_5xx"] += 1  # a genuine server error (not the simulated outage)
            raise
        if response.status_code >= 500:
            server_down["real_5xx"] += 1
        return response

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)
    try:
        res = asyncio.run(run(args.cycles, browser, f"http://localhost:{port}/", server_down))
    finally:
        server.should_exit = True
    st = res["stats"]
    expected = st["typed"] + st["voice"]
    # GET /notes returns at most 100 rows, so count on the server's database directly
    from sqlalchemy import func, select

    from app.db.models import Note
    with app.state.sessions() as db:
        on_server = db.scalar(select(func.count()).select_from(Note).where(Note.source != "seed"))
        typed_db = [t for (t,) in db.execute(select(Note.transcript).where(Note.source == "text"))]
        voice_db = db.scalar(select(func.count()).select_from(Note).where(Note.source == "audio"))
    missing = sorted(set(res["sent_texts"]) - set(typed_db))
    dupes = len(typed_db) - len(set(typed_db))
    st["server_errors_5xx"] = server_down["real_5xx"]
    ok = (on_server == expected and not missing and dupes == 0 and voice_db == st["voice"] and not st["outbox_failed"]
          and not st["server_errors_5xx"])
    summary = {
        "date": date.today().isoformat(), "result": "PASS" if ok else "FAIL",
        "notes_created": expected, "notes_on_server": on_server, "typed": st["typed"], "voice": st["voice"],
        "voice_on_server": voice_db, "missing": missing, "duplicates": dupes, **st,
        "browser": Path(browser).stem, "machine": f"{platform.system()} {platform.release()}",
        "note": "Synthetic notes, mock speech-to-text (SIMULATED), headless browser with DevTools offline "
                "emulation on one laptop. Not a physical phone or a real mobile network.",
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "report.md").write_text("\n".join([
        f"# Offline soak test — {summary['date']} — **{summary['result']}**", "",
        f"> {summary['note']}", "",
        "| Metric | Value |", "|---|---|",
        f"| Offline → online cycles | {st['cycles']} (of which {st['server_down_cycles']} were server outages (HTTP 503) instead of no connection) |",
        f"| Notes created while offline/outage | {expected} ({st['typed']} typed, {st['voice']} voice WAV) |",
        f"| Notes on the server afterwards | {on_server} (voice: {voice_db}) |",
        f"| Lost / duplicated | {len(missing)} / {dupes} |",
        f"| Page reloads with notes waiting | {st['reloads']} (notes kept in IndexedDB every time) |",
        f"| Most notes waiting at once | {st['queued_seen']} |",
        f"| Notes left marked 'could not be sent' | {st['outbox_failed']} |",
        f"| Genuine server errors (5xx, not the simulated outages) | {st['server_errors_5xx']} |",
        f"| Console exceptions | {len(st['console_exceptions'])} |",
        f"| Run time | {st['seconds']} s · {summary['browser']} · {summary['machine']} |",
        "", "Command: `python eval/offline_soak.py --cycles " + str(args.cycles) + "`", ""]), encoding="utf-8")
    print(f"{summary['result']}: cycles={st['cycles']} created={expected} on_server={on_server} "
          f"missing={len(missing)} dupes={dupes} reloads={st['reloads']} -> {out}")
    shutil.rmtree(data, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
