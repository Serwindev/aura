# Demo script — 5 minutes (T-071)

Synthetic data only. Every number below has a file in `eval/results/`; read the caveat with it.
Setup: laptop runs `.\make.ps1 phone-usb` (or `server`); phone on USB opens `http://localhost:8000`;
UI language Hindi; demo data loaded (Settings → Demo data). Mute notifications. Charge the phone.

## 0:00 — The problem (30 s)
"An ASHA in UP writes the same visit three times: her diary, the HBNC form, and later an app or the
monthly claim. A.U.R.A. lets her **say it once**, check it once, and reuses it everywhere."

## 0:30 — Today's tasks (40 s)
- Home: tasks come from the HBNC / HBYC / vaccine schedules in `rules/*.yaml`, each with *why now*.
- Tap **इलाके से (By area)**: the day's visits grouped by tola. "No GPS: she types the area once."
- Point at the yellow banner: "Advisory only; rules are not yet clinician-reviewed."

## 1:10 — Speak a note (90 s)
- Tap **Speak note** on a newborn task. Show **क्या बोलें (What to say)**: tap *अगला (Next)* as you speak.
- Say: *"आज रेखा के बेटे का नवजात भ्रमण दिन 3 किया। वजन 2 किलो 700 ग्राम है, बुखार है, दूध नहीं पी रहा।"*
- Review screen: tap a field's evidence to see the exact words highlighted in the transcript.
- Red banner: danger signs found → referral. "The app never decides; she confirms."
- Yellow **नोट में नहीं बोला गया (Not in the note)**: what this visit usually needs and was not said.
- Tap **पढ़कर सुनाएँ (Read aloud)**: the phone reads the record back (on-device voice).
- Confirm. "Her recording is deleted from the server when she confirms."

## 2:40 — Offline (40 s)
- Turn on aeroplane mode. Type or speak a note → **Waiting to send**. Reload the app: it is still there.
- Turn the network back on → it sends itself.
- Evidence: 200 offline/online cycles, 401 notes, **0 lost, 0 duplicated**
  (`eval/results/2026-11-15/offline-soak/report.md`; browser offline emulation, not a real network).

## 3:20 — Add a newborn (30 s)
- **लोग (People)** → Newborn, mother's name, birth place, area → Add. Home now shows her visits and vaccines.

## 3:50 — Reports (40 s)
- Monthly report and claim-support sheet → PDF / Excel. "Rates are national NHM rates; UP top-ups are
  not confirmed, so the sheet says *check with your ANM*. It supports a claim; it does not file one."
  Show one row: it says which visit was missed or comes next. A finished newborn series asks "Mother and baby
  safe at day 42?" and "Birth registered?"; tap Yes on both and the ₹250 moves into the total.
- **A.U.R.A. को कितना सुधारना पड़ा**: which fields she corrects most — "this grades the app, not her."

## 4:30 — Honest numbers + close (30 s)
- 20 held-out synthetic notes spoken by an **AI voice**, Sarvam speech-to-text, untuned first run:
  **17/20 notes with every critical field right, field F1 0.93**
  (`eval/results/2026-11-10/README.md`). Same audio on the offline model: 6/20.
- "These are not field numbers. Next: real voices from our team and a timed test with 5 people."
- Privacy: microphone only; no location, contacts, SMS, attendance or scoring (`docs/privacy-audit.md`, 24 checks, run in CI).

## If something fails
- No speech-to-text key / no network → type the note (same review screen) or tap an example.
- Read aloud says "no voice" → the phone lacks an offline voice for that language; switch UI to English.
