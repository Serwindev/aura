# Android app — test checklist (v1.9.0)

Synthetic data only. Tick each line and note anything that went wrong next to it. If the APK fails, use the web app instead (`.\make.ps1 phone-usb`).

## Setup (once)
- [ ] Phone: Android 8 or newer, Developer options → USB debugging ON, cable connected, "Allow" this laptop.
- [ ] Laptop: `.\make.ps1 apk` (builds) then `.\make.ps1 apk-run` (installs, forwards port 8000, starts the server).
- [ ] Wi-Fi instead of USB: `.\make.ps1 apk-wifi`, then type the printed address on the app's login screen → Save.

## Core
- [ ] App icon "A.U.R.A." with the green icon; the splash screen is green, not the Capacitor logo.
- [ ] Log in with any 10-digit number; the SIMULATED code is shown; enter it → Home.
- [ ] Record a note → Android asks for the microphone once → recording works → review → confirm.
- [ ] Type a note instead of speaking → same review.
- [ ] Airplane mode: record → the note waits on the phone → airplane mode off → it sends by itself.
- [ ] Close and reopen the app with no connection → it opens (Home from the last saved list).
- [ ] Reports → PDF and Excel → the Android share sheet opens with the file.
- [ ] Form view → "Send to ANM / Share" → share sheet with the text.

## Back button
- [ ] Form view → Back → Saved screen → Back → Home → Back → app goes to the background (does not close or crash).
- [ ] During review: Back asks "Go back?"; Cancel stays.

## Autofill (SIMULATED form only)
- [ ] Saved HBNC note → View in form order → **Get ready for autofill** → "N answers ready".
- [ ] **Turn on autofill** → Android settings → choose "A.U.R.A. visit autofill".
- [ ] **Open test form** → tap "Date of visit" → suggestion "A.U.R.A. visit: fill N answers" → tap → fields fill.
- [ ] Blank answers stay blank; "Login PIN" is never filled; Submit only clears the screen.
- [ ] Log out → open the test form again → no A.U.R.A. suggestion.

## Visit reminder
- [ ] Settings → Turn on reminder → Android asks for notifications (Android 13+) → Allow.
- [ ] Next 8 am: the notification shows only a number ("6 visits due today"), no names. To test sooner, set the phone clock forward, then set it back.
- [ ] Turn off reminder → no more notifications.

## SSBSK schedule (draft option)
- [ ] Settings → Visit schedule → SSBSK 2026 → Home shows "SSBSK newborn day …" tasks.
- [ ] People → add a newborn with "At-risk newborn" ticked → 9 visits (days 1, 3, 5, 7, 10, 14, 21, 28, 42).
- [ ] A note for "day 5" can be confirmed under SSBSK; under HBNC 2014 it is flagged.
- [ ] Switch back to HBNC 2014 → the old tasks return.

## Report back
Phone model and Android version, plus every unticked line with a short note or a screenshot (synthetic data only).
