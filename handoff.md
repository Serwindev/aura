# A.U.R.A. — handoff.md

> Session baton for Claude Code. Short, current, and honest. Update §2–§6 at the end of every session; append to §11 (never rewrite history).
> Facts: `context.md`. Plan and task IDs: `plan.md`.

## 0. Session protocol

**Start of session (≤ 5 minutes):**
1. Read this file fully. Read only the `plan.md` / `context.md` sections the next task needs (use grep/section reads; do not reload whole files).
2. Check §4 for blockers and §5 for open decisions. If a needed decision is open, ask the human before building.
3. State the plan for the task in a few lines, then proceed.

**End of session:**
1. Run tests/lint; paste the actual result in the log (do not claim "works" without output).
2. Update §2 (state), §3 (next actions), §4 (blockers), §5 (decisions), and append a §11 entry.
3. Commit with conventional messages; leave the tree clean or note what is not.

## 1. Project in five lines
- Voice-first Android app (Flutter) + FastAPI server that turns an ASHA's spoken visit note into a verified structured record, then reuses it for tasks, reports and guided data entry.
- Principle: capture once → verify once → reuse across applications.
- Focus: Uttar Pradesh workflows, Hindi primary, English second. Demo for EnVision '26 → Seva First (South Zone, Open level, Track A).
- Hard constraints: synthetic data only; no location/attendance/productivity scoring; never claim government integration we do not have.
- Deadline shape: SFIC **not submitted** (window closed 6 Nov). **Prototype v1 due 2026-11-09** (D-19): mobile web app + offline Vosk STT + rule-based extractor.

## 2. Current state (update each session)

- **Date:** 2026-11-15 · **Phase:** v1.4 **done**: add people (T-045), offline soak evidence (T-061), installable app + USB phone mode, privacy audit (T-060). LLM extractor built (T-024) but **not yet run on the real API**.
- **v1.3 (2026-11-15):** a note that cannot reach the server (no connection, 5xx, 429) is kept on the phone in IndexedDB (`server/app/web/outbox.js`) and re-sent with the same idempotency key on `online`, on app focus, every 20 s, at login, or "Send now"; then it appears as a draft to review. Bad-input errors (4xx) are kept as "Could not be sent" with a Delete button, never dropped silently. `POST /v1/notes` takes `recorded_on` (phone's date) so "aaj/kal" resolve to the day the note was spoken (future → clamped to today; > 60 days → 422). Home falls back to the last saved task list offline; service worker (`sw.js`) caches the app shell so the app reopens offline **only on localhost or a trusted HTTPS certificate** — browsers refuse service workers on the self-signed phone demo, so there the queue works while the page stays open but a reload needs the laptop. Settings shows unsent-note count; "Delete my data" also clears the phone queue.
- **Repo:** private GitHub `Serwindev/aura`; `p1-core` merged into `main` (2026-11-10). Work on `main` or a new task branch.
- **v1.1 (2026-11-10):** STT = Sarvam `saaras:v4` when `SARVAM_API_KEY` is in `server/.env` (`STT_PROVIDER=auto`), Vosk offline fallback on network/5xx/429; notes > 28 s split at the quietest point; register names + programme words sent as key terms. `GET /v1/reports/monthly?format=json|pdf|xlsx` (Summary · Visits · Tasks · Incentive); Reports screen has a Monthly report card. Privacy screen discloses Sarvam. Eval audio mode: `eval/harness.py --audio-dir … --stt sarvam|vosk`; AI-voice audio via `eval/make_tts_audio.py` (git-ignored).
- **Evidence (2026-11-10):** `eval/results/2026-11-10/README.md`. Held-out AI-voice audio, first untuned run: Sarvam critical 17/20, F1 0.93, raw WER 0.125, STT p50 0.65 s; Vosk 6/20, F1 0.70, WER 0.344. After 2 fixes seen on held-out output (now optimistic): text held-out F1 0.96, critical 18/20; Sarvam audio critical 18/20.
- **Run:** `.\make.ps1 server` → http://localhost:8000 (laptop). `.\make.ps1 phone` → prints an `https://<wifi-ip>:8443` address for a phone on the same Wi-Fi (self-signed: accept the one-time warning; allow Windows Firewall if asked; use a phone hotspot if campus Wi-Fi isolates devices). `.\make.ps1 db-reset` clears the demo. First-time setup: `.\make.ps1 setup`, `.\make.ps1 models`.
- **Phase 3 built:** simulated OTP login, `/v1` API (notes from audio/text, confirm with server-side re-validation and server-owned evidence, tasks with reschedule/dismiss, claim sheet JSON/PDF/XLSX, privacy summary/export/delete), audio deleted on confirm or discard (7-day cap), synthetic demo household with history labelled SIMULATED, mobile web app (record, audio-file upload, type, review & confirm, Home, reports, settings/privacy), Hindi default + English.
- **LLM extractor (T-024, 2026-11-15):** `server/app/extraction/llm.py` — Claude structured output (`messages.parse` + Pydantic `Proposal`: every value carries its quote) → `to_raw()` → the **same** `validate_extraction()`; the model never sets `matched_id`, confidence left null (no invented calibration). On with `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` (or `LLM_API_KEY`), `LLM_MODEL` (default `claude-haiku-5-5`), `LLM_EFFORT` (default `low`); off by default. Any failure (network, refusal, max_tokens, bad output) → rule-based, never a lost note. Settings shows which extractor runs and discloses that note **text** goes to Anthropic. Eval: `python eval/harness.py --notes … --llm <model> [--effort low]` reports F1/critical plus cost, call time and fallbacks. 15 tests with a fake client (no API spend).
- **v1.4 (2026-11-15):** **People** tab: she adds a newborn (DOB, mother — existing or new, birth place), child, pregnant woman or other; names in Hindi and English so both kinds of note match; tasks appear at once; ids `p-…` survive "Remove demo data"; edit/delete only her own people (delete blocked if notes/children exist); API `POST/PATCH/DELETE /v1/beneficiaries`; export includes `people_added`. Idempotency race fixed (two sends with one key at once → second returns the first note, was HTTP 500). `eval/offline_soak.py` (G4). App manifest + icons (installable). `.\make.ps1 phone-usb`: phone on USB opens `http://localhost:8000` → microphone, offline start and install work without the certificate warning. `scripts/privacy_audit.py` → `docs/privacy-audit.md` (G5), also a test and a CI step. CI actions bumped (checkout v7, setup-uv v10, gitleaks-action v3).
- **Not in v1:** background sync when the app is closed, ANC tasks, Flutter. (Offline queue added in v1.3.)
- **Evidence (2026-11-09):** `eval/results/2026-11-09/holdout/report.md` supersedes the 11-07 figures below: P 0.99 / R 0.90 / F1 0.94, critical 17/20 (0.85), unsupported 0.000, p50 10.5 ms (synthetic, same author, text-only). Dev F1 0.99 (overfit). Browser run in headless Edge at 390 px and 320 px, over `http://localhost` and HTTPS on the LAN IP, with a synthetic English WAV as fake mic: all flows passed, no console errors. Not tested on a physical phone.
- **Known limits:** Vosk small English misheard names in Windows TTS audio (names need picking on review, or start from a task). Hindi UI copy is not native-reviewed. Claim sheet covers HBNC/HBYC only, at national rates.
- **Built so far (all synthetic data, all offline, no API keys):**
  - Phase 1: scaffold/CI/secret scan (T-003); schema v0.1 + validator (T-020); Hindi normaliser + date resolver (T-020a); rule engine HBNC/HBYC/UIP (T-050/T-051).
  - Phase 2: STT adapters `server/app/stt/` (Vosk offline Hindi = default; mock labelled SIMULATED; Sarvam = stub needing key); rule-based extractor `server/app/extraction/rule_based.py` (LLM-shaped output + quotes → same validator); name resolution `names.py` (T-027 v0); pipeline `server/app/pipeline.py`; eval harness `eval/harness.py` (T-025, text-only); 40 dev + 20 held-out synthetic notes + registry in `eval/data/` (T-021 v0); `docs/providers.md`.
- **Numbers (only these exist; synthetic, same author — never on a slide without the caveat):** `eval/results/2026-11-07/holdout/report.md` — P 0.99 / R 0.87 / F1 0.93, critical-field match 16/20, unsupported values 0.000, text pipeline p50 10.7 ms. Dev set (tuned on) F1 0.99 — overfit, regression guard only. **Not measured:** STT WER (no recordings), LLM extraction (no key), time saved.
- **Vosk:** plumbing verified on a 22 kHz WAV (English TTS → garbage text, as expected); warm 2.9 s for 4.7 s audio on this laptop. Hindi accuracy unmeasured.
- **Demo data (v1.2):** Settings → "Remove demo data" / "Load demo data (6 beneficiaries)" (`/v1/demo`). New logins get the small set (`SMALL_DEMO` in `services.py`); the full registry stays for eval/tests via `seed_demo(..., only=None)`.
- **Last verified commands (2026-11-15):** pytest → "437 passed, 1 skipped" (skip = Vosk Hindi model not downloaded on this machine); ruff → "All checks passed!"; secret scan → "0 finding(s)".

## 3. Next actions (ordered)

1. **(human)** Rehearse on a real phone (`.\make.ps1 phone`, laptop online). Team members read the app's example notes aloud (synthetic content) → first human-voice figure for Sarvam.
2. **(human)** A native Hindi speaker reads the UI copy (`server/app/web/i18n.js`) and the monthly report PDF.
3. **(human)** Put `ANTHROPIC_API_KEY=…` in `server/.env` → run the bake-off (T-026): `cd server; .venv\Scripts\python.exe ..\eval\harness.py --notes ..\eval\data
otes_holdout.yaml --llm claude-haiku-5-5 --out ..\evalesults\<date>\holdout-llm-haiku` (then sonnet / opus). Expected cost: cents per model run (estimate; the report prints the real figure). Then write `docs/decisions/002-llm-default.md` and set `LLM_PROVIDER`.
4. **(human)** Try `.\make.ps1 phone-usb` with a real Android phone (steps print on start); add a real-looking (synthetic) newborn and record a note.
5. **(human)** Decide D-27 (Flutter deferred past the showcase) and D-28 (unsent notes on the phone have no 7-day cap).
6. Next build: bake-off + decision (T-026), then ANM review of U21–U24. Budget note: after Pro ends, work runs on ~$10 API credit — keep sessions short, `/clear` between tasks.

## 4. Blockers and waiting-on-humans

| # | Item | Owner | Status |
|---|---|---|---|
| B1 | SFIC not submitted (window closed 6 Nov) — new target date needed | Lead | open |
| B2 | API keys: Sarvam key **added** 2026-11-10 (server/.env); no LLM key yet | Lead | partly resolved |
| B3 | Blank official UP forms and claim form | Research team | open |
| B4 | ≥5 ASHA/ANM conversations | Research team | open |
| B5 | Clinician/ANM reviewer for rules | Lead | open |
| B6 | EnVision Phase 2 internal deadline | Lead | open |
| B7 | No GPU/Docker on dev laptop (AMD iGPU, 7 GB RAM) | — | worked around (D-13, D-14) |

## 5. Decisions (log; proposed defaults are NOT confirmed until marked)

| ID | Decision | Value | Status | Date |
|---|---|---|---|---|
| D-01 | Demo language | Hindi primary, English second (Tamil dropped) | **confirmed** | 2026-10-28 |
| D-02 | Focus state | Uttar Pradesh | **confirmed** | 2026-10-28 |
| D-03 | Login | Phone OTP + ASHA ID (not Google) | **confirmed** | 2026-10-28 |
| D-04 | STT default | best by bake-off (T-026) — human: "anything that is best" | **delegated to evidence** | 2026-10-28 |
| D-05 | LLM default | best by bake-off (T-026) | **delegated to evidence** | 2026-10-28 |
| D-06 | Hosting | India region / local for demo | **confirmed** | 2026-10-28 |
| D-07 | Audio retention | delete on confirm, cap 7 days | **confirmed** | 2026-10-28 |
| D-08 | Code licence | MIT | **confirmed** | 2026-10-28 |
| D-09 | Wording | "claim support", "integration-ready", "advisory" | **confirmed** | 2026-10-28 |
| D-10 | Roles | `plan.md` §8 | **confirmed** | 2026-10-28 |
| D-11 | Budget / API credits | Free tiers + Sarvam starter credits (amount [U]) + local GPU (cost near zero) | **confirmed** | 2026-10-28 |
| D-12 | Internal deadline | demo-ready 5 Nov | **missed — re-baseline pending** | 2026-11-07 |
| D-13 | Dev database | SQLite (SQLAlchemy, Postgres-ready); no Docker — `docs/decisions/001` | **confirmed** | 2026-11-07 |
| D-14 | Self-hosted ASR | Dropped on this machine (no CUDA); STT = Sarvam/Bhashini; mocks until keys | **confirmed** (follows from hardware) | 2026-11-07 |
| D-15 | SFIC | Not submitted | **confirmed** (human) | 2026-11-07 |
| D-16 | v1 form factor | Mobile web app served by FastAPI; Flutter deferred to after v1 | **confirmed** (human) | 2026-11-07 |
| D-17 | v1 STT | Vosk `small-hi-0.22` offline (Apache-2.0); Sarvam when a key exists | **confirmed** (human) | 2026-11-07 |
| D-18 | v1 extractor | Rule-based, deterministic (no LLM key); same validator; LLM later via bake-off | **confirmed** (follows from no key) | 2026-11-07 |
| D-19 | Deadline | Prototype v1 by 2026-11-09 | **confirmed** (human) | 2026-11-07 |
| D-20 | English voice | Added Vosk `small-en-in-0.4` (offline, Apache-2.0), because the human tests in English first and the Hindi model cannot transcribe English | **follows from human request** | 2026-11-09 |
| D-21 | Hindi test audio | AI-voice clips via audio-file upload; no human Hindi recording for now | **confirmed** (human) | 2026-11-09 |
| D-22 | Demo reach | Laptop + phone on same Wi-Fi via self-signed HTTPS | **confirmed** (human) | 2026-11-09 |
| D-23 | STT default | Sarvam `saaras:v4` (cloud, India; server sends audio, phone never calls a vendor); Vosk offline fallback. Supersedes D-17 default; evidence `eval/results/2026-11-10/` | **confirmed** (human: "implement the sarvam") | 2026-11-10 |
| D-24 | Reports | Monthly report in both PDF and Excel; incentive stays HBNC/HBYC (immunisation incentive is per session, rate unverified) | **confirmed** (human: both formats) | 2026-11-10 |
| D-25 | Branches | `p1-core` merged into `main` | **confirmed** (human) | 2026-11-10 |
| D-26 | Demo data | Small demo (6 beneficiaries + mothers) by default; one Settings button removes/loads it; own notes are never removed by it | **confirmed** (human) | 2026-11-10 |
| D-27 | Flutter | Defer past the showcase; demo the mobile web app with offline queue (budget: ~$10 API credit after Pro ends) | **proposed** | 2026-11-15 |
| D-29 | LLM extractor wiring | Off by default; on via `LLM_PROVIDER=anthropic`; default model Haiku 5.5 (from `.env.example`), effort low; rule-based fallback on any LLM failure; final default from bake-off (D-05) | **proposed** | 2026-11-15 |
| D-30 | Registering people | ASHA can add newborn/child/pregnant/other herself; Hindi + English name fields (no transliteration); own ids `p-` prefix (no schema migration needed) | **proposed** | 2026-11-15 |
| D-28 | Unsent notes on phone | Kept in IndexedDB until sent or deleted by the ASHA (no 7-day cap: dropping an unsent note loses a visit); disclosed in Settings; cleared by "Delete my data" | **proposed** | 2026-11-15 |

## 6. Environment and setup

**Machine change (2026-11-15):** now Python 3.11.0 + uv 0.13.8 (winget) + gh CLI 2.104 (winget, logged in as Serwindev; path `C:\Program Files\GitHub CLI\gh.exe`); Vosk models not downloaded; no `server/.env` yet (no Sarvam key on this machine). Edge headless driven over DevTools for browser checks.
**Prerequisites (previous machine):** Git ✔ (2.55); Python 3.12.10 ✔ (winget, user scope); uv 0.13.7 ✔ (winget; not on bash PATH — in Git Bash prepend `$(cygpath "$LOCALAPPDATA")/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe`); Flutter + Android SDK ✘ (phase 4); Docker ✘ (not needed, D-13); `make` ✘ → use `.\make.ps1 <target>`.

**Environment variables (names only; never commit values; keep in `.env`, provide `.env.example`):**
`DATABASE_URL`, `JWT_SECRET`, `STT_PROVIDER`, `BHASHINI_USER_ID`, `BHASHINI_API_KEY`, `SARVAM_API_KEY`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `AUDIO_RETENTION_HOURS`, `APP_ENV`.

**Makefile targets to create in T-003:** `setup`, `server`, `app`, `test`, `lint`, `eval`, `db-up`, `db-reset`, `secrets-scan`.

**Provider facts that affect code:** Sarvam REST accepts < 30 s audio (use Batch for longer); Bhashini uses a pipeline config call then an inference call with ULCA credentials; IndicConformer 600M multilingual loads via Hugging Face with `trust_remote_code` (review code before enabling); check each model's licence (context §9.1).

## 7. Repo layout (target)

```
aura/
  CLAUDE.md  plan.md  context.md  handoff.md
  app/                 # Flutter (lib/features/{home,entry,reports,settings,auth}, lib/data, lib/domain, l10n)
  server/              # FastAPI (app/{api,core,db,stt,extraction,reports,sync,audit}, tests)
  rules/               # YAML programme rules (hbnc.yaml, hbyc.yaml, uip.yaml, anc.yaml) — each with source + status
  templates/           # report templates per state/app (UP/...)
  eval/                # data/ (scripts, audio manifest, ground truth), results/, harness code
  docs/                # forms/ (blank only), research/, providers.md, decisions/, privacy.md
  Makefile  .env.example  .github/workflows/
```

## 8. Working agreement for the agent

1. **Plan first.** For any task touching more than one file, post a short plan; ask when a requirement is ambiguous or a decision (§5) is open. Do not start building a phase with unresolved blockers that affect it.
2. **Evidence discipline.** Never write an accuracy, time-saved or cost number unless it comes from a file in `eval/results/` or a cited source. Mark unknowns as unknown.
3. **Synthetic data only.** No real names, phone numbers, IDs or recordings of real patients — in fixtures, logs, screenshots or tests. If asked to use real data, stop and ask.
4. **Privacy contract (product requirement).** No location/GPS, contacts, call log, SMS, screen/other-app monitoring, attendance or productivity scoring. Permissions: microphone and notifications only. Any new permission needs explicit human approval and a decision-log entry.
5. **Secrets.** Never commit keys; `.env` only; run the secret scan before commits.
6. **Clinical content.** Programme rules live in `rules/*.yaml` with `source` and `status: draft|clinician_reviewed`. Unreviewed rules must not appear as authoritative in the UI. The app is advisory; it never diagnoses.
7. **LLM outputs are untrusted.** Validate in code: schema, ranges, evidence quote present in transcript, null when not stated. Never auto-submit; the ASHA always confirms.
8. **Integrations.** No scraping, JavaScript injection, Accessibility-service autofill or credential storage for government apps. Tier 2 is simulated and labelled `SIMULATED` in UI and docs.
9. **Scope.** Follow `plan.md` MoSCoW. Anything new needs a logged decision; propose cuts before adding.
10. **Tests with code.** Write tests alongside features; run them; report real output. If something fails, say so plainly and show the error.
11. **Token efficiency (human preference).** Read targeted sections; prefer grep/outline over full-file reads; keep summaries short; do not restate unchanged context.
12. **Honest reporting.** Distinguish *done*, *done but unverified*, *simulated*, and *not started*.

## 9. Definition of done

- **Task:** acceptance in `plan.md` §10 met; tests pass; lint clean; no secrets/PII; `handoff.md` updated.
- **Phase gate:** criteria in `plan.md` §9, backed by files in `eval/results/` or test output.
- **Evidence:** every figure on slides is traceable to a file or a source ID.

## 10. Conventions (defaults; change via decision log)

- **Dart/Flutter:** `flutter_lints`, Riverpod, feature-first folders, ARB i18n (hi, en), large touch targets (≥ 48 dp, prefer 56 dp), icons + short labels, no hard-coded strings.
- **Python:** Python ≥ 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, `ruff`, `pytest`; type hints on public functions.
- **API:** `/v1/...`, UTC ISO-8601 timestamps, UUIDs generated on device, idempotency key on every write, consistent error shape.
- **Git:** branch `t-0xx-short-slug`; conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`); small commits; PR description lists task IDs and evidence.
- **Logging:** structured, no PII, no transcripts at INFO level.
- **Docs:** decision records in `docs/decisions/NNN-title.md` (context, options, evidence, choice).

## 11. Handoff log (append-only, newest at the bottom)

### 2026-10-28 — Planning session
- Reviewed deck, workflow PDFs, team research and SFIC email; ran a research pass (voice stack, ABDM/government integration reality, UP ASHA workflow, DPDP, SFIC rules, programme schedules).
- Created `CLAUDE.md`, `plan.md`, `context.md`, `handoff.md`.
- Key findings that changed the plan: no verified API path to RCH/ANMOL (ABDM ≠ reporting channel) → Integration Ladder; "16%" stat not defensible; POC not yet run; Hindi vs Tamil mismatch; UP already has BCPM-MIS for incentives; SFIC dates conflict.
- Next: §3 items 1–3. Nothing built, nothing tested.

### 2026-10-28 — Decisions confirmed
- D-01 Hindi + English (Tamil dropped); D-03 phone OTP; D-07 ok; D-12 demo-ready **5 Nov**; D-04/D-05 = best by bake-off. `plan.md` §9 timeline compressed accordingly.

### 2026-10-28 — Plan v2.0 + research pass 2
- Renamed `handoff_4.md` → `handoff.md`, `plan_3.md` → `plan.md`.
- Human accepted all proposed defaults → D-02, D-06, D-08, D-09, D-10, D-11 confirmed.
- Research pass 2 (context S29–S34): SFIC live portal window 25 Sep–6 Nov; Sarvam ₹30/h, REST ≤30 s, Batch ≤2 h, states zero retention by default; IndicConformer-600M MIT but gated on HF; 2026 Vaani Hindi benchmark best WER ~10.6–13.7%; ANC = 4 visits + PMSMA (9th) + up to 3 HRP follow-ups; AMRIT FLW already has voice entry; `record` package sample rate depends on OS.
- Rewrote `plan.md` as v2.0: 6 phases with gates G-0…G-E, day-by-day P0–P2, new tasks T-006, T-020a, T-04C, new goal G8 (latency), new risks R-15, R-16.
- Not done: no code, no tests run.
- Next: §3 items 1–4.

<!-- Entry template
### YYYY-MM-DD — <topic>
- Done (with evidence: command + result):
- Not done / failed (with error):
- Decisions made (add to §5):
- Risks or surprises:
- Next:
-->

### 2026-11-07 — Build phase 1 (Core)
- Research refresh: SFIC registration closed 6 Nov, no further extension found (PIB / PW). New close competitor: "Sakhi" (solo Hindi voice-to-form for ASHAs, dev.to). Sarvam: STT still ₹30/h, `saaras:v4` now on REST/Batch/WebSocket, ₹1,000 signup credit.
- Machine reality differs from context §3: no NVIDIA GPU, 7 GB RAM, no Python/Docker/Flutter. Installed Python 3.12 + uv (approved). Decisions D-13/D-14/D-15 logged; `docs/decisions/001-dev-environment.md`.
- Done (evidence: `.\make.ps1 lint` → All checks passed; `.\make.ps1 test` → 292 passed; `.\make.ps1 secrets-scan` → 0 findings): T-003, T-020, T-020a, T-050, T-051 (engine side).
- New unverified items (added to context §12): U21 HBNC day numbering (assumed birth = day 1), U22 grace windows (HBNC 1 d, HBYC 30 d, UIP 28 d — placeholders), U23 danger-sign code list, U24 weight ranges outside HBNC.
- Not done: CI never ran (no remote); Hindi UI/reason strings not native-reviewed; T-027 name resolution moved to phase 2.
- Next: §3.

### 2026-11-07 — Build phase 2 (Pipeline)
- Human: prototype v1 within 2 days; no API keys; team cannot record/write test notes → D-16…D-19.
- Done (evidence: `.\make.ps1 test` → 374 passed; lint clean; secret scan 0): STT adapters (Vosk + mock + Sarvam stub), rule-based extractor, name resolution v0, pipeline, eval harness, 60 synthetic notes (40 dev / 20 held-out), registry, `docs/providers.md`, `make eval` / `make models`.
- Eval: held-out F1 0.93 (P 0.99, R 0.87), critical 16/20 — synthetic, same author, text-only. Dev 0.99 is overfit (3 real bugs fixed while debugging on it: "दौरा" = visit not convulsion; partial-word quotes; Hinglish verb-first order).
- Not done: no Hindi audio exists (Windows has no Hindi TTS voice) → WER unmeasured; Sarvam/Claude adapters not built (no keys).
- Next: §3.

### 2026-11-09 — Build phase 3 (server + mobile web app)
- Human: build straight through; laptop + phone; English first, AI voices for Hindi later → D-20…D-22.
- Done: see §2. Extractor fixes found by testing English: danger signs no longer dropped when the visit type is unknown (safety bug); "got/received" and "was given" count as given; bare "rekha baby" resolves to the child; "day seven" sets the HBNC day; a given vaccine implies an immunisation visit.
- Fonts: Noto Sans Devanagari + Noto Sans (OFL) embedded for PDFs. No Hindi font on the phone is needed.
- Not done / unverified: physical phone; Hindi speech on real or AI audio; Windows Firewall/campus Wi-Fi behaviour; native review of Hindi copy.
- Next: §3.

### 2026-11-10 — Project overview doc
- Done: wrote `docs/PROJECT_OVERVIEW.md` (tech stack, architecture, concepts, every v1 feature, API, run commands, build history, honest status). Docs only; no code changed, tests not re-run.
- Next: §3 unchanged.
- Pushed `main` and `p1-core` to private repo https://github.com/Serwindev/aura (gh CLI already authenticated as Serwindev; secret scan 0 findings before push). First CI run not yet checked.

### 2026-11-10 — v1.1: Sarvam speech-to-text + monthly reports
- Human: Vosk recognition "very worst", even English; added a Sarvam key; wants Excel + PDF reports, overview updated, branches merged and pushed → D-23…D-25.
- Done: Sarvam adapter (`server/app/stt/providers.py`, httpx; `server/.env` loader in `core/settings.py`); names as key terms; chunking; fallback. Monthly report (`server/app/reports/monthly.py`, `/v1/reports/monthly`), Reports UI, privacy disclosure. Extractor fixes: newborn mention → HBNC (confidence 0.5), "measles rubella" → MR, "102 डिग्री" → temperature, "दूध भी नहीं पी". Harness audio mode + TTS script. Tests: `server/tests/test_sarvam_reports.py` (mocked HTTP, no credits).
- Evidence: pytest 430 passed; ruff clean; live Sarvam smoke test on 2 English TTS clips was word-perfect; eval numbers in §2. PDF rendered and checked visually (en + hi).
- Not done / unverified: real human voice; physical phone; Sarvam retention is a vendor claim; CI on GitHub not checked.
- Risk: demo needs laptop internet; Vosk fallback is much weaker. Sarvam credit use is small (₹30/h audio).
- Next: §3.

### 2026-11-10 — v1.2: clean demo toggle + CI fix
- Human: demo data is "huge and mess"; wants a button to remove it and add ~6 back; merge to main; PR checks failing.
- Done: `remove_demo` / `load_demo` / `demo_status` (services), `GET/POST /v1/demo`, Settings card + toggle button (hi/en). Small set = c01, c02, c07, c08, c20, w03 + mothers (11 rows, 26 demo history notes, ~10 open tasks). CI: gitleaks failed on `pull_request` with 403 → added `pull-requests: read`.
- Evidence: pytest 433 passed; ruff clean; headless Edge (390 px) walkthrough login → Settings → remove → Home "Nothing is due" → load → 9 task cards, no console errors.
- Next: §3.

### 2026-11-15 — v1.3: offline outbox on the phone
- New machine: cloned `Serwindev/aura`; installed gh CLI + uv; `uv sync` on Python 3.11.0. Baseline: pytest 432 passed, 1 skipped (no Vosk model); ruff clean; secret scan 0.
- Human: Pro plan ends 2026-11-16; afterwards ~$10 API credit → build the costly items now; Flutter deferral proposed (D-27).
- Done: outbox (`web/outbox.js`, IndexedDB) + flush/retry in `web/app.js`; `recorded_on` on `POST /v1/notes` (`routes._recorded_on`, `create_note(recorded_on=…)`); offline Home from cached tasks; offline start from cached user/meta; service worker `web/sw.js`; Settings disclosure (D-28 proposed); hi/en strings.
- Evidence: pytest "437 passed, 1 skipped" (5 new tests in `tests/test_api.py`); ruff "All checks passed!"; secret scan "0 finding(s)". Headless Edge (390 px, DevTools offline emulation, mock STT, scratch data dir): login → offline → typed note queued + cached-list banner → "Send now" offline keeps it → online event → outbox empty, draft listed and opens in review → same idempotency key sent twice gives one draft → reload while offline opens Home + Record from the service-worker cache (localhost). No console errors.
- Not verified: a physical phone; audio recordings in the queue (only typed notes were queued in the browser test; audio uses the same path with a Blob); service worker on the self-signed HTTPS demo (expected not to register — browser rule).
- Next: §3.

### 2026-11-15 — T-024: LLM extractor (built, not yet measured)
- Done: `extraction/llm.py` (Pydantic structured output with per-value quotes → same validator), pipeline `llm=` parameter + env switch + rule-based fallback, `/v1/meta` reports the extractor, Settings disclosure (hi/en), `.env.example` (`LLM_EFFORT`), harness `--llm/--effort` with cost/latency/fallback reporting, dependency `anthropic>=2.8.0` (installed 2.8.0; `messages.parse(output_format=…)` and `ParsedMessage.parsed_output` checked against the installed SDK).
- Evidence: pytest "452 passed, 1 skipped" (15 new in `tests/test_llm_extractor.py`: hallucinated quote cleared, number/quote mismatch cleared, unknown danger code dropped, future date re-resolved, nothing-said stays null, 4 failure modes fall back, request shape/caching, cost maths); ruff clean; secret scan 0. Rule-based held-out eval re-run unchanged: F1 0.96, critical 18/20 (matches 2026-11-10).
- Not done: no real API call yet (no key) → LLM accuracy, latency and cost **unmeasured**. Server-side refusal `fallbacks` not used: the rule-based extractor is the fallback.
- Surprise: first `import anthropic` on this machine took minutes (5,600 files compiled on E:); `uv add` with the default link mode stalled — use `UV_LINK_MODE=copy`.

### 2026-11-15 — v1.4: people, offline evidence, installable, privacy audit
- Done: People tab + `/v1/beneficiaries` POST/PATCH/DELETE (`services.add_person/update_person/delete_person`, `p-` ids); idempotency race fix in `create_note` (IntegrityError → return the winning note); `eval/offline_soak.py`; manifest + icons; `make phone-usb`; `scripts/privacy_audit.py` + `docs/privacy-audit.md`; `tests/conftest.py` (shared `env` fixture); CI actions bumped + audit step.
- Evidence: pytest "474 passed, 1 skipped" (new: 19 people, 1 race, 2 audit); ruff "All checks passed!"; secret scan 0; privacy audit PASS (23 checks). Offline soak `eval/results/2026-11-15/offline-soak/report.md`: 200 cycles (8 as HTTP 503 outages), 401 notes (100 voice WAV), 401 on server, 0 lost, 0 duplicated, 20 reloads with notes waiting, 0 server errors, 69 s. The pre-fix run (kept in `offline-soak-before-race-fix/`) also delivered 401/401 but hit 29 HTTP 500s from the race. Headless Edge People check at 390/320 px: add newborn with new mother → 3 task cards on Home → typed note matched "Kavita's baby"; no horizontal overflow; no console errors.
- Not verified: physical phone (incl. `phone-usb`), real mobile network; soak is DevTools offline emulation with mock STT.
- Next: §3.
