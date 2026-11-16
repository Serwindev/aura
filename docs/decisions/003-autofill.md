# 003 — Autofill into government apps (D-34)

**Date:** 2026-11-16 · **Status:** confirmed by the human, **conditional** · **Supersedes:** the blanket ban on Accessibility autofill in `CLAUDE.md` and `context.md` §6 (point 2)

## Context
- Goal: cut the time an ASHA spends typing the same visit into a government app or register after she has already spoken it.
- The human's decision (2026-11-16): "No autofill isn't a rule … we can go with autofill if it doesn't override rules of government."
- Who enters what: UP ASHAs use **e-Kavach** [V][S13]; RCH portal / ANMOL logins are for ANMs and facility staff [V][S12]. No public API exists for any of them [U5, U6].
- The current app is a mobile web page. A web page **cannot** fill fields inside another Android app. Real autofill needs a native Android app (Flutter is deferred, D-27).

## Condition (must hold before any fill into a government app ships)
1. That app's terms of use and the state's (UP NHM) rules do not forbid it. **Not checked yet [U]** → add to T-012 (ask NHM / Argusoft).
2. She logs in herself. We never read, store or send government passwords or OTPs.
3. Only values she has already confirmed are filled. Blank stays blank.
4. She taps "Fill" on each screen, checks it, and presses Save/Submit herself. We never submit.
5. It works only on an allow-listed app and screen. It stops if the screen doesn't match the expected layout.
6. Any new Android permission is disclosed on the Privacy screen and logged as a decision.

## Ladder (cheapest and safest first)
| Step | What | Status |
|---|---|---|
| 1 | **Copy-assist** on the form view: a Copy button per answer, Copy all, and Share (WhatsApp etc.) to the ANM. No new permission. | **built** (web app, 2026-11-16) |
| 2 | **Official import route:** ask UP NHM/Argusoft whether e-Kavach accepts a QR code, deep link, CSV or intent import. This is the best route if it exists. | not started (T-012) |
| 3 | **Android Autofill service** (`AutofillService`, native app): she taps a field in the target app and picks "A.U.R.A. visit"; Android fills the matching fields. It's less invasive than Accessibility, but only works where the target app's fields support autofill. | **built 2026-11-16, SIMULATED target only** (`mobile/`, D-35): allow-list = the app's own SIMULATED test form; no government app until condition 1 is checked. Not yet run on a real phone. |
| 4 | **Accessibility fill assistant** (native app) for screens where step 3 doesn't work. It's powerful but sensitive. Google Play restricts non-accessibility uses of this API [U, check the current Play policy]. | last resort; only if 1–3 fail and the condition holds |

## Risks
- A wrong field gets filled, which is a patient-safety risk → she checks every screen; the field mapping is tested against each app version.
- The government app changes its layout → fill stops (step 5 of the condition) instead of guessing.
- Credentials or OTPs get exposed → we never read password or OTP fields.
- How it looks in the pitch → only say "autofill" for steps that are built and permitted. Today: step 1 (copy/share) is live; step 3 works only on a SIMULATED test form — say "autofill demo on a simulated form", never "fills e-Kavach".

## Step 3 as built (2026-11-16)
- `mobile/android/app/src/main/java/org/aura/asha/autofill/`: `AuraAutofillService` (Android calls it), `FillPlanner` (pure rules, JVM-tested), `VisitStore` (one visit, app-private, 12 h expiry), `AuraAutofillPlugin` (web app → native), `SimulatedFormActivity` (test screen labelled SIMULATED).
- Condition 3: only rows with a value in her **confirmed** form view are stored; blank stays blank.
- Condition 4: Android shows one suggestion "A.U.R.A. visit: fill N answers (check each one)"; nothing fills until she picks it; the service never submits and `onSaveRequest` stores nothing.
- Condition 5: allow-list by package **and** activity class; every text field id on the screen must be known for that layout, otherwise nothing is filled (layout changed → stop).
- Credentials: password, OTP, PIN, Aadhaar and captcha fields are skipped by input type and by id/hint words; they are never read or filled.
- Adding e-Kavach later = one `ScreenLayout` entry per screen in `FillPlanner.ALLOW_LIST`, only after condition 1 is met and a decision is logged.
