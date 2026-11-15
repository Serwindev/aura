# A.U.R.A. — Project Overview (everything built so far)

> Snapshot as of **2026-11-10**, branch `main` (phases 1–3 done + v1.1: Sarvam speech-to-text and monthly reports).
> This file explains the whole project in one place: the idea, the tech stack, how the pieces fit, every feature in the app, and the concepts behind them. For live status see `handoff.md`; for the plan and task IDs see `plan.md`; for sources and verified facts see `context.md`.

---

## 1. What A.U.R.A. is

**A voice-first assistant for ASHA workers** (Accredited Social Health Activists — village community health workers in India).

After a home visit, an ASHA **speaks a short note** in Hindi or English, for example:

> "आज सुनीता के बच्चे का सातवें दिन का दौरा किया, वजन 2 किलो 800 ग्राम, बुखार नहीं, ठीक से दूध पी रहा है।"

A.U.R.A. turns that into a **structured visit record** (who, which visit, weight, temperature, danger signs, vaccines given, referral, next due date). She **checks and confirms it once**, and the confirmed record is then **reused**:

- to work out **what visits and vaccines are due next** (task list),
- to produce a **monthly report** and an **incentive claim-support sheet** (PDF / Excel),
- and later, for **guided data entry** into the official apps.

**Core principle: capture once → verify once → reuse everywhere.**

**Context:** built for **EnVision '26 → Seva First** (South Zone, Open level, Track A). Focus state is **Uttar Pradesh**, Hindi first, English second.

---

## 2. Ground rules the project follows (non-negotiables)

| Rule | What it means in practice |
|---|---|
| **Synthetic data only** | Every name, phone number, household and note in the repo is made up. No real patients, no real recordings. |
| **Privacy contract** | The app asks only for **microphone** (and later notifications). No GPS/location, contacts, call logs, SMS, other-app monitoring, attendance tracking or productivity scoring. |
| **AI output is untrusted** | Whatever the extractor proposes is checked by deterministic code. Every value needs an **evidence quote** from the transcript; if something was not said, the field stays **empty (null)**. |
| **Human confirms, never auto-submit** | The ASHA always reviews and presses Confirm. Nothing is filed anywhere automatically. |
| **No fake government integration** | We do not scrape, inject JavaScript, use Accessibility autofill, or store government passwords. Anything simulated is labelled **SIMULATED**. |
| **Clinical rules are advisory** | Programme schedules live in `rules/*.yaml` with a `source` and a `status` (`draft` / `clinician_reviewed`). The app never diagnoses. |
| **Evidence for every number** | No accuracy/time-saved/cost figure without a file in `eval/results/` or a cited source. |

---

## 3. Tech stack

### 3.1 Backend (server)

| Layer | Technology | Why |
|---|---|---|
| Language | **Python 3.12** (≥ 3.11 required) | Fast to build, strong text/ML ecosystem. |
| Package manager | **uv** (`server/pyproject.toml`, `server/uv.lock`) | Fast, reproducible installs. |
| Web framework | **FastAPI** + **Uvicorn** | Typed REST API, automatic validation, serves the web app too. |
| Data validation | **Pydantic v2** | The visit-record schema is a strict Pydantic model (unknown fields rejected). |
| Database | **SQLite** via **SQLAlchemy 2** | Light enough for a 7 GB-RAM laptop with no Docker (decision D-13). Code stays PostgreSQL-ready: switching is a `DATABASE_URL` change. |
| Auth tokens | **PyJWT** (HS256) | Login returns a JWT used on every API call. |
| Speech-to-text | **Sarvam Saaras v4** (cloud, India) by default; **Vosk** (offline, CPU) as fallback | Sarvam is far more accurate on Hindi, Indian English and Hinglish (D-23); Vosk keeps the app working without internet. |
| HTTP client | **httpx** | Calls the Sarvam API from the server. |
| PDF export | **fpdf2** + **uharfbuzz**, with embedded **Noto Sans Devanagari** and **Noto Sans** fonts (OFL) | Correct Hindi text shaping in PDFs; the phone needs no Hindi font. |
| Excel export | **openpyxl** | `.xlsx` monthly reports and claim sheets. |
| HTTPS for phone demo | **cryptography** (self-signed certificate, `scripts/make_cert.py`) | Browsers allow the microphone only on `localhost` or HTTPS. |
| Rules & config | **YAML** (`PyYAML`) | Clinical schedules and ranges are data, not code. |
| File uploads | **python-multipart** | Audio file upload to the API. |

### 3.2 Frontend (mobile web app — prototype v1)

| Piece | Technology |
|---|---|
| App | Plain **HTML + CSS + vanilla JavaScript** (`server/app/web/`), no framework, no build step, served by FastAPI. |
| Audio capture | **Web Audio API** in `audio.js` — records in the browser and encodes a **16 kHz mono 16-bit WAV** itself (max 170 s). |
| Languages | `i18n.js` — all UI strings in **Hindi (default)** and **English**. |
| Layout | Mobile-first, tested at 390 px and 320 px widths, large touch targets. |

**Planned later (phase 4):** a native **Flutter** Android app (Riverpod, drift + SQLCipher encrypted local DB, offline outbox sync). Flutter was deferred so v1 could ship as a web app (D-16).

### 3.3 Quality and tooling

| Tool | Use |
|---|---|
| **pytest** + **hypothesis** | Unit, property-based and API tests (last run: **417 passed**). |
| **httpx** | FastAPI test client. |
| **ruff** | Linting (rules E, F, W, I, B, UP, SIM). |
| `scripts/secret_scan.py` | Local secret scanner run before commits. |
| **GitHub Actions** (`.github/workflows/ci.yml`) | CI: install → lint → test → secret scan, plus a gitleaks job. *(Written but never run — there is no remote yet.)* |
| `make.ps1` / `Makefile` | Task runner (Windows / Linux). |
| `eval/harness.py` | Accuracy evaluation of the extraction pipeline. |

---

## 4. Architecture — how a voice note becomes a record

```
 Phone browser                         Laptop server (FastAPI)
 ─────────────                         ───────────────────────
 Record / upload / type  ── HTTPS ──▶  /v1/notes
                                          │
                                          ▼
                                   1. STT (Sarvam saaras:v4; Vosk offline fallback) → transcript
                                          ▼
                                   2. Rule-based extractor   → "raw" proposal + evidence quotes
                                          ▼
                                   3. Validator (deterministic code decides what survives)
                                          ▼
                                   4. Name resolution        → which household member
                                          ▼
                                   DRAFT saved (SQLite) + flags
 Review screen  ◀──────────────────────────┘
 ASHA edits / confirms ── /confirm ──▶ server re-validates, keeps only server-owned evidence,
                                       stores CONFIRMED record, deletes audio, writes audit event
                                          ▼
                       Rule engine → tasks (due / overdue)   Monthly report + claim sheet → PDF / XLSX
```

Code map (`server/app/`):

| Folder / file | Responsibility |
|---|---|
| `main.py` | Builds the FastAPI app, error format, serves the web app. |
| `api/routes.py` | All `/v1` endpoints. |
| `core/schema.py` | Visit-record schema v0.1 (Pydantic). |
| `core/config.py`, `core/settings.py` | Paths, YAML loading, validation ranges, env settings, JWT secret. |
| `db/models.py` | Database tables. |
| `stt/` | Speech-to-text adapters (`base.py` interface + `providers.py`). |
| `extraction/normalize.py` | Hindi/English number & unit normaliser. |
| `extraction/dates_hi.py` | Relative date resolver ("kal", "parso", "next Monday"…). |
| `extraction/rule_based.py` | The extractor. |
| `extraction/validate.py` | The validator. |
| `extraction/names.py` | Name → beneficiary matching. |
| `pipeline.py` | Glues STT → extract → validate → names, with timings. |
| `services.py` | Business logic: create/confirm notes, tasks, audio retention, demo seed, data wipe. |
| `rules/engine.py` | Turns programme rules + history into tasks. |
| `reports/claims.py`, `reports/export.py` | Claim-support sheet and its PDF/XLSX export. |
| `reports/monthly.py` | Monthly report (visits, summary, open tasks, incentive) as JSON / PDF / XLSX. |
| `web/` | The mobile web app. |

---

## 5. Key concepts explained

### 5.1 The visit record (schema v0.1)
Defined in `core/schema.py`. One record per visit:

- `visit_type` — one of ANC, PNC, HBNC, HBYC, IMMUNIZATION, FAMILY_PLANNING, TB_FOLLOWUP, NCD_FOLLOWUP, OTHER
- `visit_date`
- `beneficiary` — what was said (`mention`) and the matched person (`matched_id`, set **by code**, never by the AI)
- `visit_index` — ANC number (1–12), HBNC day (1–60), HBYC month (1–24)
- `vitals` — weight (kg), temperature (°C), BP systolic/diastolic, haemoglobin, pulse, respiratory rate
- `danger_signs` — list of fixed codes with present yes/no
- `services_given` — IFA, calcium, vaccine, ORS, zinc, counselling, other (+ detail, e.g. "Penta 2")
- `referral` — needed?, facility, reason
- `next_due` — what and when
- `evidence` — for each filled field, the **exact quote** from the transcript that supports it

Every field is **nullable**: *not said → null*, never guessed.

### 5.2 Speech-to-text (STT) with provider adapters
`stt/base.py` defines a common interface (`SttProvider`). Implementations:

| Provider | Status |
|---|---|
| **Sarvam `saaras:v4`** (cloud) | **Default** when `SARVAM_API_KEY` is in `server/.env` (`STT_PROVIDER=auto`). Hindi (`hi-IN`) and Indian English (`en-IN`). |
| **Vosk `small-hi-0.22`** / **`small-en-in-0.4`** | Offline fallback; used automatically if Sarvam cannot be reached (the note's label then says *offline fallback*). |
| **Mock** | For tests; labelled SIMULATED. |

How the Sarvam adapter works (`stt/providers.py`):
- Audio is converted to 16 kHz mono WAV. Sarvam's REST API accepts clips **under 30 s**, so longer notes are **split at the quietest point** between 18 s and 28 s and the parts are joined.
- **Key terms** are sent with each request: the names in the ASHA's register (Latin script for English, Devanagari for Hindi) plus programme words (HBNC, BCG, OPV, Penta…). This helps the model spell names correctly.
- Network errors, rate limits and server errors fall back to Vosk; a bad key or bad request is shown as an error (never silently hidden).
- **Privacy:** the phone only talks to our server; the **server** sends the audio to Sarvam (India). Sarvam states zero data retention by default (vendor claim). The Settings → Privacy screen says this plainly. Only synthetic data is used.

Measured on 20 held-out synthetic notes spoken by an AI voice (`eval/results/2026-11-10/README.md`, first untuned run): **Sarvam got every critical field right in 17/20 notes vs 6/20 for Vosk**; field F1 0.93 vs 0.70; raw word error rate 0.125 vs 0.344; median speech-to-text time 0.65 s vs 1.7 s. AI voices are clean — this is **not field accuracy**.

### 5.3 Hindi normaliser (`extraction/normalize.py`)
Spoken notes say numbers as **words**, in two scripts and mixed languages. The normaliser turns them into values:

- Devanagari digits `०–९` → `0–9`
- Hindi & English number words: "एक सौ बीस" → 120, "nau point paanch" → 9.5
- Fractions: "साढ़े" (+½), "डेढ़" (1.5)
- Units: "2 किलो 800 ग्राम" → 2.8 kg; temperature in °F converted to °C (flagged `UNIT_CONVERTED`)
- Blood pressure: "120 by 80", "120 बटा 80"
- Ordinals: "सातवें", "seventh"
- **Folding**: removes nukta / chandrabindu / anusvara differences so spelling variants still match.

### 5.4 Date resolver (`extraction/dates_hi.py`)
Resolves relative dates **against the recording date**, in code: "आज/aaj/today", "कल/kal" (yesterday or tomorrow depending on context), "परसों/parso", "3 दिन बाद", "अगले महीने", weekdays, "15 तारीख", `dd/mm/yyyy`, ISO dates.

### 5.5 Rule-based extractor (`extraction/rule_based.py`)
No LLM key was available (D-18), so v1 uses a **deterministic, offline** extractor built from cue words and patterns. It produces output **in the same shape an LLM would** (values + evidence quotes), so a Claude-based extractor can be dropped in later and go through the same validator. It detects:

- visit type (priority-ordered cues), HBNC day / HBYC month / ANC number
- vitals near their cue words
- danger signs (with negation: "बुखार नहीं" → fever **absent**)
- services and vaccines, distinguishing **given** ("दिया", "lagaya", "was given") from **future** ("अगला", "due", "will")
- referral and facility (PHC, CHC, district hospital, SNCU…)
- next-due items and dates

Bugs found and fixed during testing include: "दौरा" means *visit*, not *convulsion*; Hinglish verb-first order; danger signs were being dropped when the visit type was unknown (a safety bug).

### 5.6 Validator — "the AI proposes, code decides" (`extraction/validate.py`)
Every proposed field passes these checks; failures are **cleared and flagged** for the ASHA to look at, never silently kept:

| Flag | Meaning |
|---|---|
| `MISSING_EVIDENCE` / `QUOTE_NOT_FOUND` | No quote, or the quote is not actually in the transcript. |
| `VALUE_MISMATCH` | The number re-derived from the quote differs from the proposed one. |
| `OUT_OF_RANGE` | Outside ranges in `rules/validation.yaml` (per visit type). |
| `UNKNOWN_DANGER_SIGN` | Code not in the fixed danger-sign list. |
| `DATE_RESOLVED` / `DATE_UNVERIFIED` / `DATE_IN_FUTURE` | Date handling results. |
| `UNIT_CONVERTED` | e.g. °F → °C. |
| `CROSS_FIELD` | e.g. systolic ≤ diastolic. |
| `OFF_SCHEDULE` | e.g. HBNC "day 5" is not a schedule day. |
| `NEEDS_CHOICE` | ASHA must pick (visit type, person, date). |
| `SCHEMA_INVALID` | Malformed field — dropped, pipeline never crashes. |

Each flag has a severity (error / warning / info) and keeps the proposed value so the screen can say "heard X — please check".

### 5.7 Name resolution (`extraction/names.py`)
Matches the spoken name to a person in the ASHA's household registry using fuzzy scoring. It understands relations: "सुनीता के बच्चे" / "rekha baby" → **the child of** Sunita/Rekha, chosen using the visit type (HBNC/HBYC/immunisation → child; ANC/PNC/family planning → mother). Uncertain matches return **candidates** for the ASHA to pick.

### 5.8 Rule engine (`rules/engine.py` + `rules/*.yaml`)
Turns programme schedules + confirmed history into a **task list** with statuses `overdue`, `due`, `due_soon`, `upcoming`, `missed`.

| Rule file | Programme | Status |
|---|---|---|
| `hbnc.yaml` | Home Based Newborn Care: visits on days 3, 7, 14, 21, 28, 42 (+ day 1 for home births) | draft |
| `hbyc.yaml` | Home Based care for Young Child: quarterly visits | draft |
| `uip.yaml` | Universal Immunisation: infant vaccine doses by age, ≥ 4 weeks between doses in a series, a missed dose never restarts the series | draft |
| `anc.yaml` | Antenatal care | **disabled** until visit timing is verified |
| `validation.yaml` | Value ranges + the fixed danger-sign list (newborn / mother / child, with Hindi + English labels) | draft |

Tasks with a recorded **danger sign** are moved to the top. Every rule file carries a `source` and is marked advisory. Some values are explicitly **unverified placeholders** (e.g. grace windows, HBNC day numbering — items U21–U24 in `context.md`) awaiting ANM review.

### 5.9 Monthly report (`reports/monthly.py`)
One report per month built **only from records the ASHA confirmed**, in Hindi or English:
- **Summary:** visits recorded, people visited, vaccine doses, visits with danger signs, referrals, overdue/missed tasks, tasks due in the next 7 days, estimated incentive.
- **Visits by type** and **vaccine doses by vaccine**.
- **Visit records:** one row per visit: date, beneficiary, visit type, day/month/number, weight, temperature, BP, Hb, danger signs, services/vaccines, referral, and how it was entered (voice / typed / demo history SIMULATED).
- **Open tasks:** overdue, missed and due-soon visits/vaccines with the reason.
- **Incentive claim support:** the claim sheet below, with its warnings.

Exported as **Excel** (one workbook, sheets *Summary · Visits · Tasks · Incentive*; the visits sheet has filters and a frozen header) or **PDF** (landscape A4, Hindi text shaped correctly). API: `GET /v1/reports/monthly?month=YYYY-MM&format=json|pdf|xlsx&lang=hi|en`.

### 5.9b Claim-support sheet (`reports/claims.py`, `templates/UP/claim_support.yaml`)
Prepares — **does not file** — an incentive claim for the month: HBNC series and HBYC visits per child, with dates and status, using **national rates** (state rates unconfirmed, shown with a warning). Verification and payment stay with the ANM/Sangini and BCPM-MIS. Exported as **JSON, PDF (Hindi-capable) and XLSX**. Immunisation is **not** in the incentive: that incentive is paid per session (mobilisation), not per visit note, and its UP rate is unverified — so it is listed as "not included" rather than guessed.

### 5.10 Integration Ladder (how we talk about government systems honestly)

| Tier | What | Status |
|---|---|---|
| 0 Export | PDF/XLSX in the shape of the register/claim | **Built** (monthly report + claim sheet) |
| 1 Guided entry | Field-by-field cards in the official app's order, one-tap copy | Planned |
| 2 Official API | Only via NHM partnership | SIMULATED only |
| 3 ABDM | ABHA verification etc. | Roadmap |

### 5.11 Evaluation harness (`eval/`)
- `eval/data/notes.yaml` — 40 **dev** synthetic notes (used for tuning → overfit, regression guard only).
- `eval/data/notes_holdout.yaml` — 20 **held-out** notes, scored without tuning.
- `eval/data/registry.yaml` — synthetic households/people.
- `eval/harness.py` — computes field precision/recall/F1, critical-field match, unsupported values, latency. **Audio mode** (`--audio-dir … --stt sarvam|vosk`) runs speech-to-text first and adds word error rate.
- `eval/make_tts_audio.py` — makes AI-voice test audio for the notes with Sarvam text-to-speech (git-ignored).

**Latest results** (`eval/results/2026-11-10/`, see its README):
- **Audio, held-out, first run (honest figure):** Sarvam — critical fields right in 17/20, F1 0.93, WER 0.125; Vosk — 6/20, F1 0.70, WER 0.344.
- **Text, held-out:** P 0.99 / R 0.92 / F1 0.96, critical 18/20, **0.000 unsupported values** (it misses rather than invents). Partly tuned: two fixes came from looking at held-out audio output.

**Caveat (always attach it):** synthetic notes by the same author as the extractor; audio is an AI voice, not real ASHA speech. **Not measured:** field speech accuracy, LLM extraction, time saved.

---

## 6. App features (prototype v1, mobile web app)

### 6.1 Login (SIMULATED OTP)
- Enter a 10-digit mobile number (+ optional name and ASHA ID).
- The server generates a 6-digit OTP valid 5 minutes, with limited attempts. There is **no SMS provider**, so the code is **shown on screen** and labelled SIMULATED.
- On first login a **synthetic demo household** is seeded (with past visits labelled SIMULATED, and a deliberately overdue vaccine for the demo story).
- Returns a JWT session token.

### 6.2 Home — task list
- Tasks from the rule engine: overdue / due / due soon, with reasons in Hindi or English (e.g. "HBNC day 7 home visit").
- Vaccines due together for one child are **merged into one card**.
- Danger-sign cases float to the top.
- Actions: **Start** a note from a task (pre-fills person and visit type), **Later** (reschedule to a date), **Dismiss**.

### 6.3 New note — three ways in
1. **Record** with the mic (browser encodes WAV in-page; audio goes only to our own server).
2. **Upload an audio file** (used for testing with AI-voice Hindi clips, D-21).
3. **Type** the note.
- Choose note language (Hindi / English) to pick the STT model.
- Built-in **example notes** to try the flow.

### 6.4 Review & confirm (the heart of the app)
- Shows **what was heard** (transcript) and lets her **play back the audio**.
- **"Check first"** list of flags at the top; tapping one scrolls to the field.
- **Evidence buttons**: tap to highlight the exact words in the transcript that support a value.
- Red **danger alert banner** when any danger sign is present.
- Editable fields: person (best candidates listed first), visit type, date (no future dates), HBNC day / HBYC month / ANC number (shown only for the matching visit type), vitals (only relevant ones shown, "more" reveals the rest), danger signs (yes/no, add/remove), services & vaccines (with a vaccine list), referral yes/no + facility, next-due items.
- **Confirm** is enabled only when required choices are made. On confirm the server:
  - re-validates everything (schema, ranges, BP cross-check, schedule days, known danger codes, person exists, date not in future);
  - **ignores any evidence sent by the client** — evidence is server-owned and kept only for fields she did not edit;
  - records which fields she **edited** (useful later for measuring extractor accuracy);
  - **deletes the audio**;
  - writes an **audit event**.
- Confirming twice is safe (idempotent). **Discard** throws the draft and its audio away.

### 6.5 Reports
- Pick a month.
- **Monthly report** card: the summary numbers on screen, with **PDF** and **Excel** download buttons (all visits, summary, open tasks, incentive).
- **Incentive claim support** below it: estimated total, one card per child, and its own PDF / Excel downloads.
- Clear warnings: estimate only, national rates, what is not included.

### 6.6 Settings & privacy
- **Demo data button** (top of Settings, labelled SIMULATED): **Remove demo data** deletes every invented beneficiary and their demo visit history, keeping the ASHA's own notes and the people those notes name; pressing it again (**Load demo data**) adds back a small set of **6 beneficiaries** — Sunita's and Rekha's newborns, Anita's baby (HBNC midway), Ishaan (MR-1 overdue), Seema's baby (HBNC complete → claim ready) and Pooja (pregnant) — plus their mothers so "Rekha's baby" still resolves. New logins get this small set.
- Switch UI language (Hindi / English); edit name and ASHA ID.
- **Privacy summary**: how many confirmed and draft notes and stored audio files exist.
- **Export my data** (JSON download).
- **Delete my data** (wipes notes, task actions, audit trail for that user, then loads the small demo).
- States the privacy contract plainly (microphone only; no location etc.).
- When Sarvam is the speech provider, says that recordings are sent to Sarvam AI (India) for speech recognition, with an offline model used when there is no internet.

### 6.7 Audio retention
Audio is deleted **on confirm or discard**, with a hard cap of **7 days** (`AUDIO_RETENTION_HOURS=168`) enforced by a purge job (D-07).

---

## 7. API reference (`/v1`)

| Method & path | Purpose |
|---|---|
| `GET /meta` | Visit types, danger-sign list, vaccines, labels for the UI. |
| `POST /auth/otp/request` | Generate simulated OTP. |
| `POST /auth/otp/verify` | Verify OTP → JWT; seeds demo data for new users. |
| `GET /me`, `PATCH /me` | Read / update profile and language. |
| `GET /beneficiaries` | The ASHA's (synthetic) people. |
| `POST /notes` | Create a draft from audio or text (supports idempotency key and task hint). |
| `GET /notes`, `GET /notes/{id}` | List / read notes. |
| `GET /notes/{id}/audio` | Play back stored audio (until deleted). |
| `POST /notes/{id}/confirm` | Human confirmation with server re-validation. |
| `POST /notes/{id}/discard` | Discard draft + audio. |
| `GET /tasks` | Computed task list. |
| `POST /tasks/{beneficiary}/{rule}/action` | Reschedule or dismiss a task. |
| `GET /reports/monthly` | Monthly report as JSON / PDF / XLSX (`month`, `format`, `lang`). |
| `GET /reports/claims` | Claim sheet as JSON / PDF / XLSX. |
| `GET /demo`, `POST /demo {action: remove\|load}` | Demo data status; remove it or load the small set (6 beneficiaries). |
| `GET /privacy/summary`, `GET /privacy/export`, `DELETE /privacy/data` | Privacy controls. |

Errors share one shape: `{code, message, details[]}` with field paths, so the UI can highlight the exact field.

### Database tables (`db/models.py`)
`users` (phone, ASHA ID, name, language) · `otps` · `people` (per-owner registry: names, category, mother link, DOB, delivery place) · `notes` (status draft/confirmed/discarded, source audio/text/seed, transcript, STT provider/confidence, draft, flags, candidates, confirmed record, edited paths, audio path, timestamps) · `task_actions` (dismiss/reschedule) · `audit_events`.

---

## 8. How to run it

```powershell
.\make.ps1 setup      # install Python deps with uv
.\make.ps1 models     # download Vosk Hindi + Indian-English models (offline fallback)
.\make.ps1 server     # http://localhost:8000 on the laptop
.\make.ps1 phone      # prints https://<wifi-ip>:8443 for a phone on the same Wi-Fi
                      #   (self-signed cert: accept the warning once; allow Windows Firewall)
.\make.ps1 db-reset   # clear the demo database
.\make.ps1 test       # pytest
.\make.ps1 lint       # ruff
.\make.ps1 eval       # run the evaluation harness
.\make.ps1 secrets-scan
```

**Speech provider:** put `SARVAM_API_KEY=<key>` in `server/.env` (git-ignored; never commit it). With a key, the laptop needs internet and Sarvam is used; without one (or with `STT_PROVIDER=vosk`), everything runs offline with Vosk. The phone only has to reach the laptop.

---

## 9. Build history

| Phase | What was built |
|---|---|
| **Planning** (28 Oct) | `CLAUDE.md`, `plan.md` v2.0, `context.md` (research, sources, verified/unverified facts), `handoff.md`. Found that there is no verified API path to RCH/ANMOL → designed the Integration Ladder instead. |
| **Phase 1 — Core** (7 Nov) | Scaffold, CI, secret scan; schema v0.1 + validator; Hindi normaliser + date resolver; rule engine for HBNC/HBYC/UIP. |
| **Phase 2 — Pipeline** (7 Nov) | Vosk/mock/Sarvam-stub STT adapters; rule-based extractor; name resolution; pipeline; eval harness with 60 synthetic notes + registry; `docs/providers.md`. |
| **Phase 3 — Prototype v1** (9 Nov) | FastAPI server + SQLite; simulated OTP login; full `/v1` API; mobile web app (record/upload/type → review → confirm → tasks → reports → privacy); audio retention; demo seed; Hindi + English UI; PDF/XLSX export with embedded fonts; self-signed HTTPS for phone use. Tested end-to-end in headless Edge at 390 px and 320 px. |
| **v1.1 — Voice + reports** (10 Nov) | Sarvam `saaras:v4` speech-to-text (chunking, key terms, offline fallback, `.env` loading); audio eval mode + AI-voice test audio; extractor fixes for cloud-ASR output (newborn → HBNC, "measles rubella", "102 डिग्री", "दूध भी नहीं पी"); monthly report (PDF + Excel) and Reports screen update; privacy disclosure; branches merged into `main`. |
| **v1.4 — People + evidence** (15 Nov) | People tab (add newborn/child/pregnant/other, tasks at once, names in both scripts); offline soak test (`eval/offline_soak.py`); idempotency race fixed; installable app + `make phone-usb`; privacy audit script/report (`docs/privacy-audit.md`) run in tests and CI. |
| **v1.3 — Offline + LLM** (15 Nov) | Offline outbox on the phone (IndexedDB, same idempotency key on retry, `recorded_on` keeps the spoken date, service-worker app shell on localhost/trusted HTTPS); LLM extractor (Claude structured output → same validator, rule-based fallback, off by default, harness `--llm`). LLM accuracy not yet measured (needs a key). |
| **v1.2 — Clean demo** (10 Nov) | Demo data button in Settings (remove / load small set of 6 beneficiaries); new logins start with the small set; CI gitleaks permission fix for pull requests. |

---

## 10. Honest status — what is NOT done or NOT verified

- **Not tested on a physical phone** yet.
- **Field speech accuracy is unmeasured**: only AI-voice audio has been tested (Sarvam 17/20 critical-correct). Real ASHA speech (noise, dialect, code-mixing) will be worse.
- **Sarvam needs internet on the laptop** and spends API credit (₹30 per hour of audio); offline fallback is Vosk, which is much weaker.
- **Hindi UI text** has not been reviewed by a native speaker.
- **Clinical rules are drafts** — need ANM/clinician review; ANC tasks disabled.
- **Incentive** covers HBNC/HBYC only, at national rates.
- **Not built yet:** background sync when the app is closed, ANC tasks, guided entry (Tier 1), Bhashini STT, Flutter app. **Built but unmeasured:** LLM extractor (needs an Anthropic key for the bake-off).
- **Offline limit:** on the self-signed phone demo the app cannot reopen with no connection (browsers refuse service workers on untrusted certificates); the note queue works while the page stays open.
- **CI**: repo is on GitHub (`Serwindev/aura`, private); first CI run not yet checked.

## 11. What comes next
1. Try on a real phone with Sarvam; record a few team members reading the example notes (synthetic content) to get a first human-voice figure.
2. Native-speaker review of Hindi UI copy.
3. When an LLM key exists: Claude extractor, then a bake-off against the rule-based extractor.
4. Phone offline queue, ANM review of unverified rules, then the Flutter app.

---

## 12. Glossary

**ASHA** — Accredited Social Health Activist · **ANM** — Auxiliary Nurse Midwife · **Sangini** — ASHA supervisor · **ANC / PNC** — ante-/post-natal care · **HBNC** — Home Based Newborn Care · **HBYC** — Home Based care for Young Child · **UIP** — Universal Immunisation Programme · **BCPM-MIS** — UP block-level incentive system · **RCH / ANMOL / U-WIN** — government health portals/apps · **ABDM / ABHA** — Ayushman Bharat Digital Mission / Health Account ID · **STT** — speech-to-text · **WER** — word error rate · **LLM** — large language model · **JWT** — JSON Web Token (login session) · **OTP** — one-time password · **Idempotent** — safe to repeat without duplicating · **Evidence quote** — the exact words in the transcript that justify a value · **SIMULATED** — label for anything that imitates a real service we don't have.
