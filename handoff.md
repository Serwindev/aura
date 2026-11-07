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
- Deadline shape: **demo-ready 5 Nov** (thin vertical slice; plan §9); showcase window from 30 Nov (dates to confirm, T-001).

## 2. Current state (update each session)

- **Date:** 2026-10-28 · **Phase:** P0 Lock (see `plan.md` §9)
- **Repo:** not created yet (T-003).
- **Built:** nothing. Planning files only: `CLAUDE.md`, `plan.md` (v2.0), `context.md`, `handoff.md`.
- **Evidence collected:** research pass 1 + 2 (context §13, S29–S34). No POC numbers exist.
- **Last verified commands:** none.

## 3. Next actions (ordered — see `plan.md` §9 day-by-day)

1. **T-001** (human) Confirm our SFIC entry status in the portal; live portal says window closes **6 Nov**.
2. **T-006** (human) Get keys: Sarvam, Bhashini ULCA userID + key, LLM API key; accept IndicConformer HF terms.
3. **T-003** Scaffold the monorepo (§7), Makefile, CI, `.env.example`, secret scan.
4. **T-020 + T-020a** Schema v0.1 + validators + Hindi normaliser + tests.
5. **T-021** (team) First 40 scripts + ground truth by 30 Oct; T-022 record them 30 Oct.
6. **T-023 → T-024 → T-025** STT adapters, extraction, eval harness; mini-eval #1 on 1 Nov.
Parallel (humans): T-004 consent form, T-005 forms, T-010 outreach, T-014 deck claim check.

## 4. Blockers and waiting-on-humans

| # | Item | Owner | Status |
|---|---|---|---|
| B1 | SFIC submission status/deadline (conflicting dates) | Lead | open |
| B2 | Bhashini ULCA userID + API key; Sarvam API key | Lead | open |
| B3 | Blank official UP forms and claim form | Research team | open |
| B4 | ≥5 ASHA/ANM conversations | Research team | open |
| B5 | Clinician/ANM reviewer for rules | Lead | open |
| B6 | EnVision Phase 2 internal deadline | Lead | open |

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
| D-12 | Internal deadline | demo-ready 5 Nov | **confirmed** | 2026-10-28 |

## 6. Environment and setup

**Prerequisites (verify versions; install latest stable):** Git; Flutter SDK + Android Studio/SDK + an emulator (and ideally one real low-end Android phone); Python ≥ 3.11 with `uv`; Docker (PostgreSQL); optional NVIDIA GPU stack for self-hosted ASR (IndicConformer/NeMo or ONNX).

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
