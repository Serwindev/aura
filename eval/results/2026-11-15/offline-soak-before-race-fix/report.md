# Offline soak test — 2026-11-15 — **PASS**

> Synthetic notes, mock speech-to-text (SIMULATED), headless browser with DevTools offline emulation on one laptop. Not a physical phone or a real mobile network.

| Metric | Value |
|---|---|
| Offline → online cycles | 200 (of which 8 were server outages (HTTP 503) instead of no connection) |
| Notes created while offline/outage | 401 (301 typed, 100 voice WAV) |
| Notes on the server afterwards | 401 (voice: 100) |
| Lost / duplicated | 0 / 0 |
| Page reloads with notes waiting | 20 (notes kept in IndexedDB every time) |
| Most notes waiting at once | 3 |
| Notes left marked 'could not be sent' | 0 |
| Console exceptions | 0 |
| Run time | 551.1 s · msedge · Windows 10 |

Command: `python eval/offline_soak.py --cycles 200`

**Superseded.** Run on commit 15307a0, before the idempotency race fix. The server returned 29 HTTP 500s (two requests with the same key at once, e.g. a reload during a send); the phone's retries still delivered every note exactly once. See `../offline-soak/` for the run on the fixed code.

