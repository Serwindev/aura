# Android app — test checklist (v1.11.0)

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

## Speak again and new people (v1.10)
- [ ] Review → **Add or change by voice** → say "temperature 38 degrees, ORS given" → Stop → only temperature and ORS change, each marked "Changed by your added recording"; the transcript shows both clips.
- [ ] Type a change in a field first, then add by voice about a different field → your typed change stays.
- [ ] Say something with no field ("okay that is all") → "Nothing new was heard"; nothing changes.
- [ ] Airplane mode → Add by voice → "needs the server" message; the draft is unchanged.
- [ ] **Record again from scratch** → confirm → record a new note → the new draft opens; Home no longer lists the old draft.
- [ ] Record "Bhagwati ki bachchi ka newborn visit day 3, weight 2.9 kg" (a name not in your list) → banner "New name heard: Bhagwati" → **Add as new person** → form opens with Newborn and mother "Bhagwati" filled → Add → the new baby is chosen for the note → Confirm works.
- [ ] Person dropdown → **+ Add new person** → empty form → Cancel → back to the review, nothing changed.

## Autofill v1.11 (any app / website, by label)
- [ ] Confirm an HBNC note → **View form** → chips show HBNC 2014 · SSBSK newborn · SSBSK mother · RCH child → each opens; blanks stay blank.
- [ ] **Copy for autofill** → "N answers copied". **Turn on autofill** → pick "A.U.R.A. visit autofill" (once).
- [ ] **Open practice app form** → tap "Date of visit" → suggestion "A.U.R.A.: fill N fields" → tap → date, weight, temperature, yes/no dropdowns fill; Login PIN stays empty.
- [ ] Chrome: Settings → Autofill services → "Autofill using another service" (once). Then **Open practice website (Chrome)** → tap a field → same suggestion → fields fill; User ID / Password stay empty.
- [ ] RCH child form: mother's name, date of birth, place of birth and vaccine dates fill.
- [ ] A.U.R.A.'s own screens never show the suggestion.
- [ ] Optional, demo only: open a real app/website form, tap a field, see what fills. **Do not press Submit.**

## Report back
Phone model and Android version, plus every unticked line with a short note or a screenshot (synthetic data only).
