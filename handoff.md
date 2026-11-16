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
- Voice-first Android app (Capacitor shell around the mobile web app, `mobile/`, D-35) + FastAPI server that turns an ASHA's spoken visit note into a verified structured record, then reuses it for tasks, reports and guided data entry.
- Principle: capture once → verify once → reuse across applications.
- Focus: Uttar Pradesh workflows, Hindi primary, English second. Demo for EnVision '26 → Seva First (South Zone, Open level, Track A).
- Hard constraints: synthetic data only; no location/attendance/productivity scoring; never claim government integration we do not have.
- Deadline shape: SFIC **not submitted** (window closed 6 Nov). **Prototype v1 due 2026-11-09** (D-19): mobile web app + offline Vosk STT + rule-based extractor.

## 2. Current state (update each session)

- **Date:** 2026-11-16 · **Phase:** v1.9 done (Android back button, visit reminder, SSBSK option — see v1.9 line); v1.8 Android app; v1.7 done (see v1.7 line) after v1.6 **done**: official form fields read (HBNC Annex 1c, SSBSK Shaishav format, UP RCH, incentives) + **form view** for HBNC notes. **Open: SSBSK 2026 changes the visit schedule (D-32).** LLM extractor built (T-024) but not yet run on the real API.
- **v1.3 (2026-11-15):** a note that cannot reach the server (no connection, 5xx, 429) is kept on the phone in IndexedDB (`server/app/web/outbox.js`) and re-sent with the same idempotency key on `online`, on app focus, every 20 s, at login, or "Send now"; then it appears as a draft to review. Bad-input errors (4xx) are kept as "Could not be sent" with a Delete button, never dropped silently. `POST /v1/notes` takes `recorded_on` (phone's date) so "aaj/kal" resolve to the day the note was spoken (future → clamped to today; > 60 days → 422). Home falls back to the last saved task list offline; service worker (`sw.js`) caches the app shell so the app reopens offline **only on localhost or a trusted HTTPS certificate** — browsers refuse service workers on the self-signed phone demo, so there the queue works while the page stays open but a reload needs the laptop. Settings shows unsent-note count; "Delete my data" also clears the phone queue.
- **Repo:** private GitHub `Serwindev/aura`; `p1-core` merged into `main` (2026-11-10). Work on `main` or a new task branch.
- **v1.1 (2026-11-10):** STT = Sarvam `saaras:v4` when `SARVAM_API_KEY` is in `server/.env` (`STT_PROVIDER=auto`), Vosk offline fallback on network/5xx/429; notes > 28 s split at the quietest point; register names + programme words sent as key terms. `GET /v1/reports/monthly?format=json|pdf|xlsx` (Summary · Visits · Tasks · Incentive); Reports screen has a Monthly report card. Privacy screen discloses Sarvam. Eval audio mode: `eval/harness.py --audio-dir … --stt sarvam|vosk`; AI-voice audio via `eval/make_tts_audio.py` (git-ignored).
- **Evidence (2026-11-10):** `eval/results/2026-11-10/README.md`. Held-out AI-voice audio, first untuned run: Sarvam critical 17/20, F1 0.93, raw WER 0.125, STT p50 0.65 s; Vosk 6/20, F1 0.70, WER 0.344. After 2 fixes seen on held-out output (now optimistic): text held-out F1 0.96, critical 18/20; Sarvam audio critical 18/20.
- **Run:** `.\make.ps1 server` → http://localhost:8000 (laptop). `.\make.ps1 phone` → prints an `https://<wifi-ip>:8443` address for a phone on the same Wi-Fi (self-signed: accept the one-time warning; allow Windows Firewall if asked; use a phone hotspot if campus Wi-Fi isolates devices). `.\make.ps1 db-reset` clears the demo. First-time setup: `.\make.ps1 setup`, `.\make.ps1 models`.
- **Phase 3 built:** simulated OTP login, `/v1` API (notes from audio/text, confirm with server-side re-validation and server-owned evidence, tasks with reschedule/dismiss, claim sheet JSON/PDF/XLSX, privacy summary/export/delete), audio deleted on confirm or discard (7-day cap), synthetic demo household with history labelled SIMULATED, mobile web app (record, audio-file upload, type, review & confirm, Home, reports, settings/privacy), Hindi default + English.
- **LLM extractor (T-024, 2026-11-15):** `server/app/extraction/llm.py` — Claude structured output (`messages.parse` + Pydantic `Proposal`: every value carries its quote) → `to_raw()` → the **same** `validate_extraction()`; the model never sets `matched_id`, confidence left null (no invented calibration). On with `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` (or `LLM_API_KEY`), `LLM_MODEL` (default `claude-haiku-5-5`), `LLM_EFFORT` (default `low`); off by default. Any failure (network, refusal, max_tokens, bad output) → rule-based, never a lost note. Settings shows which extractor runs and discloses that note **text** goes to Anthropic. Eval: `python eval/harness.py --notes … --llm <model> [--effort low]` reports F1/critical plus cost, call time and fallbacks. 15 tests with a fake client (no API spend).
- **v1.4 (2026-11-15):** **People** tab: she adds a newborn (DOB, mother — existing or new, birth place), child, pregnant woman or other; names in Hindi and English so both kinds of note match; tasks appear at once; ids `p-…` survive "Remove demo data"; edit/delete only her own people (delete blocked if notes/children exist); API `POST/PATCH/DELETE /v1/beneficiaries`; export includes `people_added`. Idempotency race fixed (two sends with one key at once → second returns the first note, was HTTP 500). `eval/offline_soak.py` (G4). App manifest + icons (installable). `.\make.ps1 phone-usb`: phone on USB opens `http://localhost:8000` → microphone, offline start and install work without the certificate warning. `scripts/privacy_audit.py` → `docs/privacy-audit.md` (G5), also a test and a CI step. CI actions bumped (checkout v7, setup-uv v10, gitleaks-action v3).
- **v1.5 (2026-11-15):** Read aloud on review/saved (Web Speech, **on-device voices only**, `localService`). Guided recording: "What to say" list per programme (HBNC/HBYC/UIP/ANC/other) with Next — prompts only, still one free recording. Review shows "Not in the note" (vitals usual for the visit type + danger signs for HBNC/HBYC). `GET /v1/reports/edits?month=` + Reports card: fields she corrected most (demo notes excluded) — framed as grading the app, not her. People have an optional `area` (ward/tola; child inherits mother's; demo people get invented areas); tasks carry `area`; Home toggles By date / By area (no GPS). DB: additive column migration `_add_missing_columns` (people.area). Docs: `docs/demo-script.md`, `docs/hard-questions.md`, `docs/public-forms.md` (B3 leads, PDFs not yet opened).
- **v1.6 (2026-11-15):** Blank-form research (B3, partly resolved): fields copied to `docs/form-fields.md`, facts + sources S35–S39 in `context.md` §8. **Form view**: `GET /v1/notes/{id}/form` + "View in form order" on the saved screen for HBNC notes — her confirmed record in the order of HBNC Annexure 1c (`rules/forms/hbnc_home_visit.yaml`, `app/forms.py`); temperature shown in °F and °C; unstated = blank, never "No"; questions the app does not capture say "fill yourself". Not an integration. National incentive rates in the claim config re-checked against NHSRC Apr 2024 (match).
- **v1.7 (2026-11-16):** Claude removed. The LLM extractor now uses **free providers only** through one OpenAI-compatible adapter (`LLM_PROVIDER=ollama|groq|gemini|openai_compat`, httpx, JSON schema in the prompt → same validator; rule-based fallback; `anthropic` dependency dropped) (D-33). Settings discloses note text only when the provider is not on this machine. Home has a big **Add voice note** button above the bottom bar. Form view has **Copy** per answer, **Copy all** and **Send to ANM / Share** (Web Share, else copy): step 1 of the autofill ladder (D-34, `docs/decisions/003-autofill.md`).
- **v1.8 (2026-11-16): Android app** (`mobile/`, Capacitor 7, D-35): debug APK `org.aura.asha` 1.8.0 bundles `server/app/web` (copied by `mobile/copy-web.mjs`; pages load from `http://localhost` inside the APK, so the app opens offline). API calls go to a settable server (default `http://localhost:8000` via `adb reverse`; Wi-Fi address on the login screen/Settings); server CORS allows only `http://localhost`. Native: mic permission, share sheet for form text and reports (PDF/XLSX), **Android Autofill service** (D-34 step 3) with a **SIMULATED** test form as the only allow-listed target: confirmed answers only, blank stays blank, password/OTP/PIN fields never read or filled, unknown field ids → stop, answers expire after 12 h and are cleared on logout/Delete my data. Permissions: INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS; no backup. Privacy audit now checks the manifest. `.\make.ps1 apk | apk-run | apk-wifi`. Web app unchanged in a browser (fallback). **Not run on a real phone or emulator yet** (no emulator hypervisor on this laptop).
- **v1.9 (2026-11-16):** Android **back button** goes one screen back (form → saved → home; asks before leaving review or a recording; on Home the app goes to the background) — native `MainActivity` → `auraBack()`. **Visit reminder** (opt-in, Settings, Android only, D-36): local notification at 8 am for the next 3 days with only the **number** of visits due, no names; planned on the phone from the last task list; cancelled on logout/Delete my data. **SSBSK 2026 schedule as an option** (D-32 default still open; default unchanged = HBNC 2014/HBYC 2018): Settings → Visit schedule; `rules/ssbsk_newborn.yaml` (days 3/7/14/42, +1 home birth; at-risk 1/3/5/7/10/14/21/28/42) and `rules/ssbsk_child.yaml` (3–36 months), status draft [S36]; person flag **at-risk** (People, SSBSK only); note validation follows her schedule; claim sheet stays on 2014 rules. `docs/security-checklist.md` (T-064 draft, unsigned). CI builds the APK (artifact `aura-debug-apk`). APK 1.9.0. Test list: `docs/android-test-checklist.md`.
- **v1.10 (2026-11-16, after first real-phone test on a realme 16 Pro 5G, Android 16 — human: "everything is working fine"):** review screen **"Add or change by voice"**: she speaks again; `POST /v1/notes/{id}/add` (audio or text) runs the same pipeline on the new clip only and changes **only fields the clip carries a quote for** (newer speech wins; danger signs upsert by code, services append, next-due upsert by name); the machine draft is updated (so these are not counted as her corrections), the clip text is appended to the transcript, the added audio is never stored; each changed field gets a `VOICE_ADDED` info flag; nothing new → 422 `NOTHING_NEW`; needs the server (offline → message, nothing lost). **"Record again from scratch"**: new recording, old draft discarded only after the new note is sent or queued. **New names:** `new_names()` in `extraction/names.py` (narrow patterns: "X ki bachchi", "X ke ghar", "visited X", "baby of X", "X devi/ji", "X se mili"; known people and common words excluded) → `new_names` on draft notes → review banner "New name heard … Add as new person" opens the People form **prefilled** (newborn/child with new mother X on child visits, else the person) — she saves; it is then picked for the note. Person dropdown has "+ Add new person". APK 1.10.0. (D-37) Fix: on Android 15+ the app was drawn under the status bar (edge-to-edge) → `mobile/capacitor.config.json` `android.adjustMarginsForEdgeToEdge: "auto"`.
- **v1.11 (2026-11-16): autofill like a password manager (D-38).** Forms in the app: HBNC 2014 (Annex 1c) + **SSBSK Form 3 newborn, Form 4 mother, Form 6+5 young child** + **RCH child tracking CH-1/CH-2** (`rules/forms/*.yaml`, status draft; person rows from her saved person, dose dates = earliest confirmed note giving that dose). Saved note → **View form** → pick a form (chips) → Copy / **Copy for autofill** / **Open practice app form** (native SIMULATED screen built from the form) / **Open practice website (Chrome)** (`/sim-portal/<form>`, SIMULATED, labels only, login box). Each row has `fill` (bare value: dd-mm-yyyy, 2800, 99.5, Yes/No) + `match` words (en+hi). Native: `FieldMatcher` (label/hint/HTML label > view id/name; one answer per field; yes/no into dropdowns and checkboxes), any app or web page except A.U.R.A.'s own screens; login/password/OTP/PIN/Aadhaar skipped. Chrome needs Settings → Autofill services → "Autofill using another service" [U: exact menu wording on her Chrome version]. APK 1.11.0.
- **v1.12 (2026-11-16): reopen and edit saved visits; forms ask for more (D-39).** Home → **Recent visits** (last confirmed, newest first) and People → **Visits** open a saved visit → View form · **Edit note** · Read aloud. Edit = same review screen (typing + voice); stays confirmed until she confirms again; record replaced, tasks re-derived, audit `edited` with changed paths (no values). Review has an optional **Forms also ask** card (Yes/No taps, numbers, *Say them*). View form lists what that form **still needs** (tap/type or **Fill missing by voice** → proposals with quotes → **Save answers**). Catalogue `rules/forms/details.yaml` (19 visit details, 4 person details: sex, birth weight, child RCH ID, mother's RCH ID — saved on the person, asked once). Voice = keyword rules in `extraction/details.py` (no LLM; will miss some phrasings). APK 1.12.0.
- **Not in v1:** background sync when the app is closed, ANC tasks (rules unverified, T-013), Flutter (replaced by Capacitor, D-35). (Offline queue added in v1.3.)
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

0. **(human)** Test v1.12 (checklist section "Reopen, edit and form details v1.12"), then v1.11 autofill (checklist section "Autofill v1.11"): practice app form, practice website in Chrome, then (optional, demo only, no Submit) a real app. Then v1.10 items. v1.9 core checked on a realme 16 Pro 5G (Android 16) on 2026-11-16: "everything is working fine". Now test v1.10 (new section in `docs/android-test-checklist.md`). Earlier: test the APK on a real Android 8+ phone with `docs/android-test-checklist.md`: `.\make.ps1 apk-run` (USB debugging on). Check: login, record (mic prompt), confirm, form view → Get ready for autofill → Turn on autofill → Open test form → pick "A.U.R.A. visit". Report anything broken; the web app (`.\make.ps1 phone-usb`) is the fallback.
1. **(human)** Rehearse on a real phone (`.\make.ps1 phone`, laptop online). Team members read the app's example notes aloud (synthetic content) → first human-voice figure for Sarvam.
2. **(human)** A native Hindi speaker reads the UI copy (`server/app/web/i18n.js`) and the monthly report PDF.
3. **(human)** Free LLM bake-off (T-026): install Ollama + `ollama pull qwen2.5:3b` (local), and/or put a free Groq/Gemini key + `LLM_MODEL` in `server/.env` → `cd server; .venv\Scripts\python.exe ..\eval\harness.py --notes ..\eval\data\notes_holdout.yaml --llm ollama --out ..\eval\results\<date>\holdout-llm-ollama`. Keep rule-based as default unless an LLM beats F1 0.96 / critical 18/20. Then write `docs/decisions/002-llm-default.md`.
3b. **(human)** Autofill condition (D-34): ask UP NHM / Argusoft whether e-Kavach terms allow assisted fill, and whether it has any import route (QR, deep link, CSV).
4. **(human)** Find out whether UP uses SSBSK 2026 visits yet (ask an ASHA facilitator / block community mobiliser) → decide D-32. Also: UP claim form + state rates (still not public).
5. **(human)** Try `.\make.ps1 phone-usb` with a real Android phone (steps print on start); add a real-looking (synthetic) newborn and record a note.
6. **(human)** Decide D-27 (Flutter deferred past the showcase) and D-28 (unsent notes on the phone have no 7-day cap).
7. Next build: bake-off + decision (T-026), then ANM review of U21–U24. Budget note: after Pro ends, work runs on ~$10 API credit — keep sessions short, `/clear` between tasks.

## 4. Blockers and waiting-on-humans

| # | Item | Owner | Status |
|---|---|---|---|
| B1 | SFIC not submitted (window closed 6 Nov) — new target date needed | Lead | open |
| B2 | API keys: Sarvam key **added** 2026-11-10 (server/.env); no LLM key yet | Lead | partly resolved |
| B3 | Blank official UP forms and claim form | Research team | partly resolved 2026-11-15 (national forms read; UP claim form + rates still missing) |
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
| D-32 | Visit schedule | Default stays HBNC 2014 / HBYC 2018. SSBSK 2026 **built as an opt-in option** (Settings) on 2026-11-16 because the human asked to build everything; making it the default still needs UP's adoption confirmed | **default: proposed — needs human**; option built | 2026-11-16 |
| D-31 | Correction stats | Show per-field correction counts to the ASHA only, as an app-quality signal; never a score of her, never sent to supervisors | **proposed** | 2026-11-15 |
| D-30 | Registering people | ASHA can add newborn/child/pregnant/other herself; Hindi + English name fields (no transliteration); own ids `p-` prefix (no schema migration needed) | **proposed** | 2026-11-15 |
| D-33 | LLM extractor providers | Free only: Ollama (local), Groq / Gemini free tiers, any OpenAI-compatible server; Claude removed. Rule-based stays the default until a free LLM beats it | **confirmed** (human: "go for any free alternatives") | 2026-11-16 |
| D-34 | Autofill into government apps | Allowed if it does not break the app's terms / government rules; she logs in, taps to fill, submits herself; no credential reading/storage; ladder in `docs/decisions/003-autofill.md`. Step 1 (copy/share) built | **confirmed, conditional** (human) | 2026-11-16 |
| D-35 | Android form factor | Native app now (human); built with Capacitor 7 around the same web app (Claude's choice, reversible); autofill step 3 on a SIMULATED form only; `docs/decisions/004-android-app.md`. Supersedes D-16/D-27 for Android | **confirmed** (native app) / **proposed** (Capacitor) | 2026-11-16 |
| D-36 | Visit reminder | Opt-in daily local notification (8 am), count only, no names, planned on the phone; adds POST_NOTIFICATIONS (+ RECEIVE_BOOT_COMPLETED, WAKE_LOCK so reminders survive a reboot) — within the contract (microphone + notifications) | **proposed** (built; human asked for "everything") | 2026-11-16 |
| D-37 | Speak again + new people | Review has both "Add or change by voice" (only fields the new clip states change, with quotes) and "Record again from scratch"; a name not in her list → prefilled add-person form, she saves (never auto-created) | **confirmed** (human picked "Both buttons" + "Prefilled form") | 2026-11-16 |
| D-39 | Reopen/edit saved notes; extra form details | Saved visits reopen from Home (Recent visits) and People; Edit = reopen and re-confirm (record replaced, audit lists changed paths). Extra form questions: optional card on review + still-missing list per form with voice; person-level details (sex, birth weight, RCH IDs) stored on the person. Voice for these = deterministic keyword rules, every answer shown with its quote, she saves | **confirmed** (human picked: Home + People; reopen and re-confirm; review optional; on the person) | 2026-11-16 |
| D-38 | Autofill scope (demo) | Any app/website, matched by field label (password-manager style); government-terms check deferred until before real use; demos stop before Submit. Supersedes D-34 conditions 1 and 5 | **confirmed** (human: "Remove D-34 … we would only test till the form filling") | 2026-11-16 |
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
8. **Integrations.** No scraping, JavaScript injection or credential storage for government apps. Autofill into a government app only if it does not break that app's terms or government rules: she logs in, taps to fill and submits herself (D-34, `docs/decisions/003-autofill.md`). Tier 2 is simulated and labelled `SIMULATED` in UI and docs.
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

### 2026-11-15 — v1.5: read aloud, guided recording, correction stats, areas, demo docs
- Done: see §2 v1.5 line. Files: `server/app/web/{app,i18n}.js`, `style.css`, `sw.js` (cache v3); `services.edit_stats`, `demo_area`, `_clean_area`; `routes` `/reports/edits`, area on people; `db/models._add_missing_columns`; `extraction/names.Person.area`; privacy audit now lists speech synthesis (on-device only).
- Evidence: pytest "479 passed, 1 skipped" (new: 3 area tests incl. old-DB migration, 2 edit-stats); ruff clean; secret scan 0; privacy audit PASS (24 checks). Headless Edge (390/320 px): By-area groups shown with status pills; guide Next moves highlight; review shows "Not in the note: Temperature (°C), Danger signs"; read-aloud text "Baby girl of Sunita. HBNC. HBNC day 3. Weight 2.8. No danger signs marked" and speech started; saved screen has read-aloud; Reports card "1 / 1 notes confirmed with no changes"; person added with area shown; no overflow; no console errors.
- Not verified: read-aloud on a real Android phone (needs an offline Hindi voice installed); Hindi wording of new strings not reviewed by a native speaker.
- Next: §3.

### 2026-11-15 — v1.6: official form fields + form view
- Done: downloaded and read HBNC guidelines 2014 (Annexures 1a–1c rendered as images, pp. 16–22), SSBSK 2026 (schedule pp. 19/36, Shaishav app format pp. 112–118), NHSRC ASHA incentives Apr 2024, Assam claim form (layout only), UP RCH register manual (Section III). HBYC guideline site and nhm.gov.in July 2025 list timed out. Wrote `docs/form-fields.md`, `context.md` §8 + S35–S39, `rules/forms/hbnc_home_visit.yaml`, `server/app/forms.py`, route, UI form view, `tests/test_forms.py`.
- Evidence: pytest "484 passed, 1 skipped" (5 new); ruff clean; secret scan 0; privacy audit PASS (24). Headless Edge (Hindi UI): note with "99 डिग्री फ़ारेनहाइट" → form shows "99.0 °F (37.2 °C)", jaundice stated absent → "नहीं", not-feeding → E2 "हाँ" and A5 "नहीं", unstated signs blank, 8/30 filled; no overflow at 390/320 px; no console errors.
- Finding: SSBSK 2026 integrates HBNC+HBYC with a new schedule; our rules use the old one → D-32.
- Next: §3.

### 2026-11-16 — v1.7: free LLM adapter, Home record button, copy/share form, autofill decision
- Human: no Claude for extraction, free alternatives only (D-33); a record button at the bottom of Home; autofill is allowed if it doesn't break government rules (D-34); progress report as a shareable page.
- Done: `extraction/llm.py` rewritten as an OpenAI-compatible adapter (presets ollama/groq/gemini/openai_compat, `LLM_BASE_URL`), `anthropic` removed from `pyproject.toml`/`uv.lock`; `/v1/meta` adds `extractor_cloud`/`extractor_provider`; harness `--llm <provider>` reports tokens instead of cost; privacy audit allow-lists api.groq.com and generativelanguage.googleapis.com; Home `.record-fab`; form view copy/copy-all/share; `docs/decisions/003-autofill.md`; CLAUDE.md, plan.md, context.md wording updated for D-34; sw cache v5.
- Evidence: pytest "488 passed, 1 skipped"; ruff "All checks passed!"; privacy audit PASS (25 checks); secret scan 0.
- Not verified: the Home button and copy/share were **not** checked in a browser this session; no free LLM run yet (no Ollama installed, no free key) → LLM accuracy still unmeasured.
- Next: §3.

### 2026-11-16 — v1.8: Android app (Capacitor) + Autofill service (SIMULATED target)
- Human: "Check whether you could make Android app rn … change everything into native app format … try to integrate autofill … if anything goes wrong, we can still use the web app."
- Found: Android SDK (API 31–36, build-tools 35), Android Studio JBR 21, Node 22, cached Gradle 8.14; no emulator hypervisor; no phone attached. Chose Capacitor (reuses the tested web app) over a Flutter rewrite (D-35).
- Done: `mobile/` (Capacitor 7.6, @capacitor/share), `server/app/web/native.js` (NATIVE flag, server base URL, share/file/autofill glue), app.js native branches (server card on login/Settings, autofill card on form view, share/download via Android, no service worker in-app, autofill cleared on logout/delete), i18n hi+en, CORS for `http://localhost` only, native Java (`autofill/`: service, planner, store, plugin, SIMULATED form), manifest (mic, no backup, autofill service bound by BIND_AUTOFILL_SERVICE), launcher icon + splash from the web icon, make targets, privacy audit Android checks, docs 003 (step 3 built) + 004.
- Evidence: Gradle "BUILD SUCCESSFUL", JVM tests FillPlannerTest 6/6 pass; `aapt dump permissions` → INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS (+ Android's internal DYNAMIC_RECEIVER_NOT_EXPORTED); pytest "491 passed, 1 skipped" (+2 CORS, +1 audit); ruff clean; privacy audit PASS (29 checks). Headless Edge with fake native bridge, pages on `http://localhost`, API on :8000: login shows server card; Home loads over CORS; form view shows autofill card; "Get ready" sends only the 4 confirmed answers (date, day 3, 2.8 kg, BCG yes) to `setVisit`.
- Not verified: the APK on a device (mic in WebView, autofill popup, share sheet). Autofill into the app's own SIMULATED activity is expected to work (Android does not exclude the service's own package) but is untested.
- Next: §3 item 0.

### 2026-11-16 — v1.9: back button, visit reminder, SSBSK option, security checklist, Android CI
- Human: "Do we need any other features? … work on everything and I will test it later, after the finished build."
- Done: native back handling (`MainActivity` OnBackPressedCallback → `auraBack()`); `@capacitor/local-notifications` 7.0.7 + `ic_stat_aura`; reminder card in Settings; SSBSK rule files, `SCHEDULES` in `core/config.py`, `load_ruleset(schedule=)`, `validation_config(schedule=)`, `users.schedule` + `people.at_risk` (additive migration), `PATCH /v1/me {schedule}`, `at_risk` on beneficiaries; claim sheet pinned to 2014 rules; UI chips + at-risk checkbox/tag; fixed the saved screen crashing when the people list was not loaded (found by the back-button test); privacy audit reads plugin manifests; `docs/security-checklist.md`; CI `android` job; `docs/android-test-checklist.md`.
- Evidence: pytest "502 passed, 1 skipped" (+11 `test_ssbsk.py`); ruff clean; privacy audit PASS (29); secret scan 0; Gradle BUILD SUCCESSFUL, FillPlannerTest 6/6; APK 1.9.0 permissions = INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS, RECEIVE_BOOT_COMPLETED, WAKE_LOCK, POST_NOTIFICATIONS. Headless Edge with fake native bridge: back form→saved→home→false; reminder → requestPermissions, cancel, schedule (3 notifications, count-only text); schedule switch → `ssbsk2026`, Home shows `ssbsk_*` tasks; at-risk checkbox appears.
- Not verified: anything on a real device (notification delivery, back button, mic, autofill popup). CI android job not yet run on GitHub (not pushed).
- Next: §3 item 0.

### 2026-11-16 — v1.10: speak again on review, suggest new people (first real-phone test)
- Human tested v1.9 on a realme 16 Pro 5G (Android 16, USB; needed USB tethering off + File transfer + re-authorising adb): "everything is working fine". Asked for (1) a suggestion to create a person when the note names someone not in the list, (2) editing/adding details by speaking again. Chose "Both buttons" and "Prefilled form" (D-37).
- Done: `new_names()` + `NewName` (names.py); `add_to_note()` (services.py) with person re-resolved using the draft's visit type when the clip has none; `POST /v1/notes/{id}/add`; shared `_note_input()` checks (routes.py); `new_names` on draft note views; People form refactored into `personForm()`/`bindPersonForm()` and reused on review; review voice card, new-name banners, "+ Add new person" option, record-again flow (`replaceNoteId`, `dropReplaced()`); hi+en strings; CSS; APK 1.10.0.
- Evidence: pytest "511 passed, 1 skipped" (+9 `tests/test_voice_add.py`); ruff "All checks passed!"; Gradle BUILD SUCCESSFUL; `node --check` app.js/i18n.js OK.
- Not verified: the new review UI on the phone or in a browser run (phone dropped off USB before reinstall); new-name detection on real Sarvam transcripts (patterns tested on synthetic text only).
- Next: §3 item 0 (v1.10 checklist section).

### 2026-11-16 — v1.11: autofill by field label, 4 more official forms, SIMULATED targets
- Human: pushed v1.10; asked for a form view per programme, "copy for autofill", and Google-Passwords-style autofill in the government apps/portals; chose targets "both app and website", forms "RCH child tracking, SSBSK young child, SSBSK newborn + mother"; removed the D-34 terms gate for the demo (D-38).
- Done: `app/forms.py` (multi-form, `fill`/`input`/`match`, person + dose context), `rules/forms/{ssbsk_newborn,ssbsk_mother,ssbsk_child,rch_child}.yaml` + match words on HBNC; `form_context()`; `GET /v1/notes/{id}/forms`, `?form=` on `/form`; `app/sim_portal.py`; native `FieldMatcher`, rewritten `FillPlanner`/`VisitStore`/`AuraAutofillService`, dynamic `SimulatedFormActivity` (old XML layout removed), plugin `openBrowser`; web form picker + autofill card; strings hi/en; CLAUDE.md + decision 003 updated.
- Evidence: pytest "521 passed, 1 skipped" (+10 `test_autofill_forms.py`); ruff clean; privacy audit PASS (29); JVM FillPlannerTest 9/9.
- Not verified: autofill on the phone (practice app screen, Chrome page, any real app); whether Chrome on her phone offers third-party autofill; label matching on real government screens (unknown layouts).
- Next: §3 item 0.

### 2026-11-16 — v1.12: reopen and edit saved visits, extra form details (D-39)
- Human: "you can't really open the note again once it settled" (bug) and "collect the necessary data that the form needs … missing details should be shown"; chose Home + People, reopen and re-confirm, review card optional, person details on the person.
- Done: `rules/forms/details.yaml` + `app/extraction/details.py` (clauses, topic/problem/fine/negation words, numbers with °C→°F and g→kg, quotes); `VisitRecord.extras`; person columns `sex`, `birth_weight_kg`, `rch_id` (added by `_LATER_COLUMNS`); pipeline + voice-add fill extras (mother's temperature no longer read as baby's); confirm validates extras; `POST /notes/{id}/edit`, `confirm {edit: true}`, `POST /notes/{id}/details/voice` (proposals only), `POST /notes/{id}/details` (save; quote kept only if in transcript); `GET /notes?status=&beneficiary_id=&limit=`; `person_label` on notes; `/meta.details`; forms: 30 "fill yourself" rows became askable (`kind: detail` / person fields), form view returns `missing`; practice portal uses dropdowns for them. Web: Recent visits, person visits, saved view from list, Edit note, Forms also ask card, still-missing card with voice.
- Evidence: pytest "531 passed, 1 skipped" (+10 `test_form_details.py`, 2 tests updated for the new behaviour); ruff clean; privacy audit PASS (29); Gradle BUILD SUCCESSFUL; APK 1.12.0 installed on the realme (adb "Success"); live `/v1/meta` lists 24 details.
- Not verified (at the time; phone test done in the next entry): the new screens on the phone, Hindi wording of the new strings and of the voice words, real speech for the detail questions.
- Next: §3 item 0.

### 2026-11-16 — v1.12 tested on the phone over USB; plain-language overview
- Human: asked whether the agent can test on their phone over USB, and for an easier project overview with visuals and mind maps.
- Method: `adb` taps/typing/screenshots + Chrome DevTools protocol to the debug WebView (`adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>`; small Python driver using `websockets`). Speech itself cannot be spoken by the agent: the mic was tested by recording room noise (server returned 422 NOTHING_NEW as expected), and spoken sentences were sent as text through the same endpoints.
- Verified on realme RMX5120 / Android 16, APK 1.12.0: Recent visits → Open → saved screen; Edit note → tap + voice-add → re-confirm (weight 2.9, `extras.exclusive_bf` in edited paths, quote kept for mother's temperature); new HBNC note → 4 details captured from text; RCH child form → still-missing list (4) → Hindi sentence gave sex/birth weight/RCH ID with quotes, mother's RCH typed on the real keyboard → saved → form filled, missing list empty; People → baby → visits.
- Found + fixed (commit 7cd1759): a newborn visit could be linked to an adult (the mother) with no warning, which hides the child forms. Review now warns and offers "Add <name>'s baby" with the mother preselected. Also: "Saved visit" heading and Today tab when reopening.
- Docs: `docs/PROJECT_OVERVIEW.md` rewritten in plain language (v1.12); new `docs/overview.html` (mind map, steps, screens, forms, promises, status), also published as a private artifact.
- Note: realme asks for an on-screen "Install" confirmation for every adb install.

### 2026-11-16 — Autofill checked on the phone; demo video
- Human: deadline **18 Nov 2026**; "Go ahead with your testing and I need a demo video to send to my team".
- Found + fixed (commit 65ffa6a): the practice app form showed no autofill suggestion. Causes: the first focused field was the PIN (never filled, so no dropdown); labels set at runtime are dropped from what Android shows the autofill service; Spinners had no autofill options. Fix: fields carry their label as content description, Spinners expose Yes/No, the column takes first focus; count-only debug log (`AuraAutofill: fields= answers= matched=`, never content).
- Verified on realme RMX5120 / Android 16: practice app form `matched=7` of 7 answers → "A.U.R.A.: fill 7 fields (check each one)" → date 16-11-2026, day, Yes filled, PIN empty. Practice website in Chrome: same 7/7, date + day + Yes/No dropdowns filled, User ID and Password empty.
- Limitation to remember: a real native app whose labels are plain text (not hint/description) may not match; web pages pass labels through, so they match.
- Demo video: `exports/AURA_demo_2026-11-16.mp4` (git-ignored; 2:08, silent, English captions, made-up "Rekha Devi's baby"). Story: Today → typed Hindi note (agent cannot speak; caption says typed) → review with quotes → Forms also ask → confirm → View form → RCH still-missing (Girl, 2.9 kg) → save → practice website autofill → stops before Submit → Today. Recorded with the phone's own screen recorder (adb `screenrecord` is blocked on this realme: "Permission denied"); sound switched off. Scripts in the session scratchpad (not kept).
- Not verified: autofill in a real (non-practice) app.

### 2026-11-16 — Incentive claim sheet: what to do next + HBNC payment conditions
- Human: asked what the incentive page does ("I think that feature isn't fully developed yet"); chose "Fix rows + conditions" (not immunisation money before 18 Nov).
- Finding: the claim support sheet (Reports) counted HBNC (₹250 per finished series) and HBYC (₹50 per visit) only; rows said "missing visit" without which visit; HBNC conditions [S17] were a printed note only, so a finished series always showed "ready".
- Done: `reports/claims.py` rows now carry `todo` (missed / late visit with due date, next visit with date; en/hi) and, for a finished HBNC series, `checks` {safe_d42, birth_registered}. New statuses `check_conditions` (₹250 shown as `pending`, not in total) and `not_eligible` (a condition is No). Person columns `safe_d42`, `birth_registered` (`_LATER_COLUMNS`); `POST /v1/beneficiaries/{id}/claim-checks` (audit `claim_checks_set`; children only; works for demo people). Reports screen: to-do lines, Yes/No questions on the row (tap again clears), "+ ₹N after you confirm the conditions". PDF/Excel: new status labels, column "What to do". Template's `hbnc_conditions` text replaced by a comment.
- Evidence: pytest "537 passed, 1 skipped" (+6 in `test_claims.py`; `test_claim_sheet_demo_month` now walks check → ready → not payable, 422 adult, 404 unknown); ruff clean; privacy audit PASS (29); APK rebuilt and installed; on the phone, made-up "Kiran Devi's baby" (6 HBNC visits 3 Oct–11 Nov) showed "Check conditions" ₹0 + ₹250 pending → real taps Yes, Yes → "Ready" ₹250; Hindi rows checked.
- Not done (deliberate): full immunisation ₹100, complete immunisation ₹75, LBW quarterly ₹50 [S37] — need the official "fully immunised" vaccine list verified first. Hindi wording still needs a native reviewer.
- Demo data note: the full demo seed's c20 (Seema's baby) now starts at "Check conditions"; tap Yes twice in the demo to show ₹250.
