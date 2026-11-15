# Hard questions — short, honest answers (T-074)

Numbers only from `eval/results/` (with their caveat) or cited sources. If unsure, say "we have not measured that".

**1. How accurate is it with real ASHA voices?**
We don't know yet. Our figures use synthetic notes spoken by an AI voice: 17/20 notes fully right on
critical fields, F1 0.93, untuned (`eval/results/2026-11-10/README.md`). Real recordings from volunteers
are the next step. That is why every field needs her confirmation and shows the words it came from.

**2. What if it gets a danger sign wrong?**
It is advisory. Danger signs are highlighted in red and need her tap; nothing is sent anywhere
automatically. Missing a sign is the worst case, so the "Not in the note" list prompts her to ask about
danger signs on every newborn/child visit where none were mentioned.

**3. Does it connect to RCH / e-Kavach / U-WIN / ANMOL?**
No. We have no government integration and do not claim one. It prepares the information in the order she
needs; she enters it herself. No scraping, autofill or stored government logins.

**4. Where does the data go?**
Audio: phone → our server → Sarvam (India) for speech-to-text, deleted when she confirms (7-day cap).
Note text goes to an LLM only if that is switched on (it is off by default). Microphone is the only
permission. See `docs/privacy-audit.md`.

**5. Is this surveillance of ASHAs?**
No location, attendance, contacts, call logs or productivity scores; the privacy audit checks this in CI.
The "how often it needed correcting" card measures the app's mistakes, and only she sees it.

**6. Offline villages?**
Notes wait on the phone and send themselves later: 401/401 delivered in a 200-cycle soak test, 0 lost or
duplicated (`eval/results/2026-11-15/offline-soak/report.md`). That was browser offline emulation on a
laptop, not a real network. Speech-to-text itself needs a connection unless the offline model is used,
which is much weaker (6/20 vs 17/20 on the same audio).

**7. Low-literacy users?**
Speak instead of type; "What to say" prompts; read-aloud of the record before confirming; Hindi first.
Not yet tested with ASHAs — usability testing with ≥5 people is planned.

**8. Are the clinical rules right?**
They follow the national HBNC/HBYC/UIP schedules as we read them, with sources in each `rules/*.yaml`, and
are marked *not yet reviewed by an ANM or clinician*. A clinician review is a stated blocker.

**9. Incentive amounts?**
National NHM rates only; UP top-ups are not confirmed, so the sheet says to check with the ANM. It is
claim *support*, not a claim.

**10. Cost per ASHA?**
Not measured. Speech-to-text is a per-minute cloud cost; we will report it after the field pilot instead of
guessing.

**11. Why a web app, not Android?**
Fastest way to test with users; it installs to the home screen and works offline. A native app is deferred
(decision D-27, proposed).

**12. What is real and what is simulated?**
Real: speech-to-text, extraction, review, tasks, reports, offline queue. Simulated: OTP login, demo people,
and all data (synthetic). Simulated parts are labelled `SIMULATED` in the app.
