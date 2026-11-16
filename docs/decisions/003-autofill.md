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
| 3 | **Android Autofill service** (`AutofillService`, native app): she taps a field in the target app and picks "A.U.R.A. visit"; Android fills the matching fields. It's less invasive than Accessibility, but only works where the target app's fields support autofill. | needs native app; prototype after D-27 |
| 4 | **Accessibility fill assistant** (native app) for screens where step 3 doesn't work. It's powerful but sensitive. Google Play restricts non-accessibility uses of this API [U, check the current Play policy]. | last resort; only if 1–3 fail and the condition holds |

## Risks
- A wrong field gets filled, which is a patient-safety risk → she checks every screen; the field mapping is tested against each app version.
- The government app changes its layout → fill stops (step 5 of the condition) instead of guessing.
- Credentials or OTPs get exposed → we never read password or OTP fields.
- How it looks in the pitch → only say "autofill" for steps that are built and permitted. Today, only step 1 exists.
