# A.U.R.A. — Project Overview

> Plain-language snapshot as of **16 Nov 2026 (v1.12)**. A visual version with a mind map is in
> [`docs/overview.html`](overview.html) (open it in a browser). Live status: `handoff.md`. Plan and task IDs: `plan.md`.
> Facts and sources: `context.md`. All names and numbers in examples are made up.

---

## 1. The idea in one minute

**Who it's for:** ASHA workers, the village health workers in Uttar Pradesh who visit mothers, newborns and young children.

**The problem:** after each visit she writes the same facts into registers, apps and claim forms, often more than once.

**What A.U.R.A. does:**

1. **She speaks** one short note after the visit, in Hindi, English or a mix.
   > “आज सुनीता देवी के बच्चे का सातवें दिन का दौरा किया, वजन 2 किलो 800 ग्राम, बुखार नहीं।”
2. **A.U.R.A. fills in a visit record:** who, which visit, weight 2.8 kg, no fever…
3. **She checks it once.** Every value shows the words it came from. She fixes anything by typing, tapping or speaking again.
4. **The record is reused:** her list of what's due next, her monthly report and claim sheet, and the official forms
   (shown in form order, ready to copy or autofill).

**Rule of thumb: say it once, check it once, use it everywhere.**

Built for **EnVision '26 → Seva First**. Hindi first, English second.

---

## 2. Mind map

```
                                   ┌─ Speak in Hindi or English
                     ┌─ Capture ───┼─ …or type, or upload audio
                     │             └─ Queued if the network drops
                     │             ┌─ Each value shows the words it came from
                     ├─ Check ─────┼─ Danger signs and doubts flagged
                     │             └─ She confirms once (and can edit later)
                     │             ┌─ Today's tasks and reminders
                     ├─ Reuse ─────┼─ Monthly report and claim sheet (PDF / Excel)
        A.U.R.A. ────┤             └─ Read aloud on the phone
                     │             ┌─ 5 official form layouts
                     ├─ Forms ─────┼─ "Still missing" questions, by tap or voice
                     │             └─ Autofill by field label (practice targets SIMULATED)
                     │             ┌─ Mothers, newborns, children
                     ├─ People ────┼─ Sex, birth weight, RCH IDs saved once
                     │             └─ Each person's visits
                     │             ┌─ Only microphone and notifications
                     └─ Promises ──┼─ No location, contacts, calls or SMS
                                   ├─ Never submits anything
                                   └─ Made-up data only
```

---

## 3. Promises (the project's non-negotiables)

| Promise | What it means |
|---|---|
| Made-up data only | No real patients, IDs or recordings anywhere in the project. |
| Two permissions | Microphone and notifications. No location, contacts, call logs, SMS, other-app watching, attendance or scoring. |
| Shows its source | Every value carries the exact words it came from. Not said → left empty, never guessed. |
| She decides | Nothing is saved, filled or sent without her tap. A.U.R.A. never presses Submit. |
| No fake integration | No scraping, no injected scripts, no government passwords. Practice stand-ins are labelled **SIMULATED**. |
| Advice only | Visit and vaccine schedules live in `rules/*.yaml` with a source and a review status (draft until a clinician reviews). |
| Numbers need proof | No accuracy or time-saved figure without a file in `eval/results/` or a cited source. |

---

## 4. The screens

| Screen | What she can do |
|---|---|
| **Today** | See visits and vaccines due (overdue first, by status or by area), unsent notes, and **Recent visits** to reopen. |
| **Note** | Record, type or upload. A short guide of what to say for each visit type. |
| **Review** | Check who, visit type, vitals, danger signs, services, referral and next dates. **Add or change by voice.** Optional **Forms also ask** card (baby kept warm? only breastfed? eyes?). Warns if a baby's visit is linked to an adult and offers to add the baby. |
| **Saved visit** | **View form**, **Edit note** (same review screen; stays saved until she confirms again), Read aloud. |
| **View form** | The visit in an official form's order. **Still missing** list: tap, type or say the answers, check them, save. Copy, share, autofill, practice form. |
| **People** | Add mothers, newborns, children; see each person's details and visits. |
| **Reports** | Monthly report and incentive claim-support sheet (PDF / Excel); how often she corrected the app. Each claim row says which visit was missed or comes next; a finished newborn series asks the two payment conditions (safe at day 42, birth registered) and counts only when both are Yes. |
| **Settings** | Language, server address, demo data, privacy notice, delete her data. |

---

## 5. How it works

```
 Phone app (Android)                    Laptop server (Python)
 ───────────────────                    ──────────────────────
 Record / type / upload  ───────────▶  1. Speech to text (Sarvam cloud, or Vosk offline)
 (outbox if offline)                    2. Find the facts with fixed rules, each with its quote
                                        3. Double-check: ranges, dates, name → her people list
 Review screen  ◀────────────────────── DRAFT + flags
 She edits / confirms ─────────────────▶ re-checked, saved as CONFIRMED, audio deleted, audit log
                                        4. Schedules → tasks · reports · form views · autofill answers
```

- **Speech to text:** Sarvam (best on Hindi and Hinglish; needs a key and internet on the laptop) or Vosk (offline, weaker).
- **Finding the facts:** deterministic rules (`server/app/extraction/`), not an AI model. An AI-model adapter exists but is
  off and unmeasured. Extra form questions use keyword rules (`rules/forms/details.yaml`, `extraction/details.py`).
- **Checking:** `extraction/validate.py`. A value without a matching quote is dropped.
- **Tasks:** `rules/engine.py` + `rules/hbnc.yaml`, `hbyc.yaml`, `uip.yaml` (drafts).
- **Forms:** `rules/forms/*.yaml` (HBNC 2014, SSBSK Form 3, Form 4, young child, RCH CH-1/CH-2) + `server/app/forms.py`.
- **Autofill (demo stage, D-38):** Android autofill service in `mobile/android/…`. She opens the other app and logs in
  herself, taps a field, picks "A.U.R.A.: fill N fields", and checks each one. Password, OTP, PIN and login fields are
  never read or filled. Practice targets: an in-app form and a website at `/sim-portal/`, both **SIMULATED**.

---

## 6. Tech in brief

| Part | Built with |
|---|---|
| Server | Python 3.12, FastAPI, Pydantic v2, SQLite via SQLAlchemy (Postgres-ready), PyJWT |
| Speech | Sarvam `saaras:v4` (cloud), Vosk (offline) |
| Reports | fpdf2 + HarfBuzz with Noto fonts (Hindi in PDFs), openpyxl (Excel) |
| Phone app | Plain HTML/CSS/JS (`server/app/web/`) inside a Capacitor 7 Android shell (`mobile/`) |
| Quality | pytest + hypothesis, ruff, secret scan, privacy audit script, GitHub Actions CI |

Folders: `server/app/` (API, pipeline, rules engine, reports, web app) · `rules/` (schedules, validation, forms) ·
`mobile/` (Android) · `eval/` (test notes, harness, results) · `docs/` (this file, checklists, decisions) · `scripts/`.

---

## 7. How to run it

```powershell
.\make.ps1 setup         # install Python packages
.\make.ps1 server        # http://localhost:8000 on the laptop
.\make.ps1 apk           # build the Android app (APK)
.\make.ps1 apk-wifi      # server reachable from the phone over Wi-Fi
.\make.ps1 test          # automated tests
.\make.ps1 secrets-scan  # before every commit
```

Phone over USB: install the APK, then `adb reverse tcp:8000 tcp:8000`. Put `SARVAM_API_KEY` in `server/.env` (never committed)
to use Sarvam. Without it, Vosk runs offline.

---

## 8. Where it stands

**Working and checked**
- v1.12 on a real phone (realme 16 Pro, Android 16), tested over USB on 16 Nov:
  - reopen a visit from Today and People;
  - edit and re-confirm;
  - the "Forms also ask" card and the "still missing" list;
  - Hindi voice answers with their quotes, saved onto the child;
  - the warning when a baby's visit is linked to an adult.
- Automated tests: 537 passed, 1 skipped (Hindi Vosk model not downloaded on this laptop).
- On 20 made-up test notes the key fields were right in 17
  (`eval/results/2026-11-09/holdout/report.md`; same author wrote notes and rules, so this is optimistic).
- Privacy audit: all 29 checks pass (`docs/privacy-audit.md`).

**Not yet known**
- Accuracy with real ASHA voices, noise and dialects (only AI-voice audio tested so far).
- Hindi wording, reviewed by a native speaker.
- Schedules, reviewed by an ANM or doctor (ANC tasks are off).
- Autofill on real government apps (government permission is needed before real use).
- Whether an AI model beats the fixed rules (bake-off not run).
- The claim sheet uses national rates for HBNC/HBYC only (UP rates not public). Immunisation and low-birth-weight
  follow-up incentives are not counted yet: the official "fully immunised" vaccine list must be checked first.

---

## 9. How it grew

| Version | Date | Added |
|---|---|---|
| Planning | 28 Oct | Plan, research, verified facts; no official API route to RCH → honest "integration ladder" |
| v1.0 | 7–9 Nov | Rules, pipeline, server, web app: record → review → confirm → tasks → reports |
| v1.1–1.2 | 10 Nov | Sarvam speech-to-text, monthly report, demo data button |
| v1.3–1.5 | 15 Nov | Offline outbox, People, read aloud, guided recording, areas, privacy audit |
| v1.6–1.7 | 15–16 Nov | Official form view, copy/share, free AI-model adapter |
| v1.8–1.9 | 16 Nov | Android app with autofill service, reminders, back button |
| v1.10 | 16 Nov | Speak again on review; suggest adding new people |
| v1.11 | 16 Nov | Autofill by field label; SSBSK and RCH forms; practice website |
| v1.12 | 16 Nov | Reopen and edit saved visits; "still missing" form questions by tap or voice; person details |

---

## 10. Words used here

**ASHA**: Accredited Social Health Activist (the user).
**ANM**: Auxiliary Nurse Midwife (her supervisor).
**HBNC / HBYC**: home visits for newborns and for young children.
**SSBSK**: the 2026 newborn and child home-visit programme.
**UIP**: the national vaccine schedule.
**RCH**: the mother-and-child register and portal (each person has an RCH ID).
**Evidence quote**: the exact words a value came from.
**Autofill**: Android filling another app's form from a saved visit, after she taps.
**SIMULATED**: a practice stand-in for something real we don't have.
