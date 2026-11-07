# A.U.R.A. — context.md

> ASHA Unified Reporting Assistant. Stable project knowledge: facts, evidence, constraints.
> Last research pass: 2026-10-28. Read order for the agent: `CLAUDE.md` → `handoff.md` → `plan.md` → this file (only the sections you need).

## 0. How to read this file

| Tag | Meaning |
|---|---|
| **[V]** | Verified from a cited source `[S#]` (see §13). Safe to build on. |
| **[U]** | Unverified, assumed, or conflicting. Do NOT build on it without checking. Listed again in §12. |
| **[D]** | A decision still to be locked (see `plan.md` §14). |

Rule: if a fact is not in this file, do not invent it. Mark it [U] and ask.

---

## 1. Summary

A.U.R.A. is a voice-first Android assistant for ASHA workers (India's community health workers). The ASHA speaks a visit note in her own language; the app turns it into a structured record; she confirms it once; the record is stored once and reused to (a) generate her due-visit task list, (b) produce monthly summaries and incentive-claim support sheets, and (c) help her enter data into the government apps she already has to use. Principle: **Capture once → Verify once → Reuse across applications.** It works *for* the ASHA, not *on* her: no GPS, no attendance, no productivity scoring.

Competition path: EnVision '26 (LICET, Phase 2 working model) → Seva First Innovation Challenge (SFIC), South Zone, theme *Swasth & Samavesh Bharat*, Open level, Track A (product/technology).

---

## 2. Competition context

### 2.1 SFIC facts [V][S1][S2]
- Run by Ministry of Education + AICTE + UGC; nodal institute IISc Bengaluru. Our edition: **South Zone** (AP, Karnataka, Kerala, Tamil Nadu, Telangana, A&N, Lakshadweep, Puducherry).
- 5 themes; ours: **Swasth & Samavesh Bharat** (health, well-being, assistive tech, inclusion). 2 tracks: **A** product/technology, **B** business model/governance. 3 levels: Junior, Technical, **Open** (UG and above).
- **Open level expectation:** "a demonstrated prototype or pilot with a credible pathway to deployment, supported by cost, beneficiaries, timeline, impact and scalability."
- **Evaluation framework:** relevance, originality, feasibility, cost, impact, scalability, quality of solution. Screening by NITs, final evaluation at IISc Bengaluru.
- Submission = "a short, structured concept with supporting material where available" (a demo link/video helps).
- Prizes (portal): ₹10 L / ₹5 L / ₹3 L, applicable *per category* (School / ITI-Polytechnic / University-Colleges). The LICET email says "per theme". [U] — does not change the plan.
- Support for selected teams: mentorship, lab access, incubation, pilot support.

### 2.2 Dates — conflicting, confirm now [U]
| Item | What sources say |
|---|---|
| Submission window | Live portal (fetched 2026-10-28, re-checked same day): **25 Sep – 6 Nov 2026**; page says "indicative schedule, to be confirmed at formal notification" [V][S2]. Older/cached copies and news: closes 24 Oct. Maharashtra zone extended to 30 Oct. |
| State screening by NITs | From 7 Nov 2026 (live portal) — "indicative, to be confirmed". |
| Showcase / finale window | 30 Nov – 15 Dec 2026. FAQ: finale at IISc Bengaluru 10–17 Dec. Ministry launch release: New Delhi, December. |

**Action:** the team must confirm in the portal today whether our entry is submitted and what the final deadline is (task T-001).

### 2.3 Our status (as reported by the team lead; confirm) [U]
Team ranked about 10th of ~70 at EnVision '26 and was selected by LICET for SFIC nomination. The LICET email (1 Oct 2026) says best EnVision projects are nominated by LICET and must show a working prototype [S3].

---

## 3. Team and constraints [U — confirm]

- 7-member team (names on deck): Anto Jaffrey Heron, Danish, Arockiya Jeffrey Lobo, Meshak, Ajayshiya, Cindralla, Arokiya Serly Serwin. Reported to be first-year students from different departments, i.e. mixed (mostly non-CS) skills. A mentor/lead drives the engineering with Claude Code.
- Existing research ownership (from team compilation): Login—Meshak; Homepage—Danish; Data Entry—Serwin; Report Generation—Heron (Serwin assisting); Settings—Jeffrey. Apps: Danish (e-Kavach, RCH, U-WIN), Cindralla (Nikshay, HMIS, FP-LMIS), Ajayshiya (IDSP, e-Sanjeevani, BCPM-MIS). Autofill/API: Heron + Serwin.
- Time: ~4.5 weeks from 28 Oct to the 30 Nov showcase window start.
- Team is based in Chennai; focus state is Uttar Pradesh. **No direct access to UP ASHAs yet.**
- Developer machine has a local RTX-class GPU (usable to self-host open ASR models for evaluation/demo).

---

## 4. Problem and evidence

### 4.1 Claims we can defend
| Claim | Evidence |
|---|---|
| ~1 million ASHAs nationally | Deck; widely cited; ASHABot paper cites ~1 million [V][S20]. |
| UP has ~1.6 lakh ASHAs | Parliament reply table lists 160,575 (+9,515 in an adjacent column, labels unconfirmed = 170,090 total) [V][S15]; Vikaspedia: "over 1.5 lakh" [V][S14]. |
| ASHAs are incentive-based, not salaried | Government incentive structure [V][S17][S20]. |
| Documentation is a real burden | ASHA diary usability study, 57 ASHAs (2025) [V][S23]; ethnography of paperwork vs care time [V]; "double work" reporting [V][S22]. |
| ASHAs prefer voice over typing | ASHABot field work: ASHAs "never typed", used voice dictation/voice notes; typing questions took much longer than voice in Haryana and Telangana [V][S20]. |
| Monthly reporting burden | KhushiHealth (vendor claim): monthly reports of ~300 columns can take up to a week [V as a claim][S21]; HMIS data due by the 10th of the next month [V][S27]. |
| Surveillance backlash is real | Haryana "Shield 360" MDM app, 2021, 15,000+ ASHAs protested, app withdrawn [V][S22]; Maharashtra "Hajeri" photo-attendance, 2025 [V][S22]; Telangana GPS requirement protests, 2025 [V][S22]. |

### 4.2 Claims in the deck that must be fixed before anyone judges them
| Deck claim | Problem | Fix |
|---|---|---|
| "16% of ASHA daily time is spent on repetitive workflow, duplicate entries…" | No source on deck. The only matching figures found are from a 2007 West Bengal study of **female health workers (ANMs)**: 26% of time on documentation; a cited review noted 16% preparing reports [V][S23]. That is not about ASHAs and not about duplicate entry. | Remove, or replace with our own measurement (T-011) and say "n = X". |
| "ASHAs are on strike across India through 2026" | Not verified in this research. | Soften to what we can cite (documented protests 2021, 2025) or verify. |
| Kerala 2025: ~30,000 ASHAs, sit-in from 10 Feb 2025, 71 days, 500+ km march | From the deck; not independently checked. | Cite a news source or drop the numbers. |
| POC slide with [N], [X]%, [A] min, [B] sec | **Placeholders; no POC has been run.** | Run the eval (E2) and fill with real numbers, or remove the slide until then. |
| "no new R&D", "low per-user cost" | Cost not computed. | Use unit economics in §9.5. |
| "Sync everywhere … Govt Portals: RCH, ANMOL, ASHA-Nidhi" | No public third-party API path found for these (§6). "ASHA-Nidhi" name unverified (diagram export is blurry). | Reframe as the Integration Ladder (`plan.md` §6). |

---

## 5. Users and workflow reality

- **ASHA**: local woman, honorary/incentive-based; home visits (ANC, HBNC, HBYC, immunisation mobilisation, TB/NCD follow-up), VHND mobilisation, due-lists, claims incentives monthly. Keeps paper: Village Health Register, delivery forms, home-visit forms, ASHA diary, drug-kit stock register, birth-preparedness plan formats [V][S26]. Many keep rough notes, then copy into official forms; forms often missing or partially filled [V][S26].
- **ANM**: supervises ASHAs; does RCH/ANMOL data entry; verifies ASHA work. RCH portal logins are only for health staff, issued via district/state RCH cell [V][S12].
- **ASHA Sangini / Facilitator**: supervises ASHAs (UP: ~9.5k) [V/U][S15]; BCPM, BAM at block level [V][S14].
- **NHM / state health dept**: buyer/owner of systems; data fiduciary in practice (§10).
- **UP HBNC**: state guidelines require ASHAs to use **three formats** per newborn visit; formats had repetition [V][S26].
- **Devices**: ASHAs use WhatsApp and voice features [V][S20]. UP smartphone ownership, Android version, RAM [U] — design for low-end (assume Android 8–12, 2–3 GB RAM) until measured.

### 5.1 UP-specific systems [V unless tagged]
- **e-Kavach**: UP Dept of Health app for health functionaries, built by Argusoft on its mPHM/MEDPlat platform; data in UP State Data Centre; ASHA training delivered via e-Kavach (Basti, Aug 2026) [V][S13]. Family folders, maternal/child health, NCD, nutrition, referrals (team research).
- **BCPM MIS**: web-mobile platform mapping geographies, facilities and health workers (ASHA, Sangini, ANM, MoIC, BCPM, BAM) with a module that digitises ASHA and Sangini incentive payments; reported 35% rise in average monthly incentive per ASHA [V][S14]. **Implication: UP already has a digital incentive claim path. A.U.R.A. must prepare/support claims, not replace or duplicate it.** Exact claim workflow [U].
- Past UP mHealth: ReMiND (CRS) ASHA/Sangini apps; mSakhi (IntraHealth) [V][S14-adjacent]. Evidence that apps were adopted when they were job aids.

---

## 6. Systems landscape and integration reality

### 6.1 Systems table
| System | Main users | What it does | Third-party API? | A.U.R.A. tier (see plan §6) |
|---|---|---|---|---|
| e-Kavach (UP) | ASHA, ANM, others | Family folders, MCH, NCD, nutrition, referral | [U] none found | Tier 0/1 |
| RCH portal | ANM/facility staff (logins via district) | Pregnancy/child tracking; due lists; used for JSY and ASHA payments "wherever possible"; 30 states/UTs; Rajasthan & Gujarat push via **state web services** [V][S11][S12] | None public found. State-to-state web-service integration exists, which is an NHM-level channel, not an app-developer one [V/U] | Tier 0/1, Tier 2 only via NHM |
| ANMOL | ANM (tablet) | Writes to RCH DB; syncs when online; 6 states as of 2018 (UP not listed then) [V][S12] | [U] none found | Out of scope |
| U-WIN | Vaccinator, delivery-point, mobilizer (ASHA) modules | Immunisation registry; ABDM-aligned | Co-WIN had public + protected third-party APIs [V][S24]; U-WIN equivalent [U] | Tier 1; Tier 2 if available |
| BCPM-MIS | Block/ASHA/Sangini | Incentive payment, mapping | [U] | Tier 0 (claim support sheet) |
| Nikshay | TB staff, ASHA | TB notification, treatment adherence | [U] | Tier 1 (later) |
| HMIS | Facility staff | Monthly service data; due by the 10th [V][S27] | n/a | Monthly summary output |
| FP-LMIS, IDSP/IHIP, e-Sanjeevani | Various | Logistics, surveillance, telemedicine | [U] | Not in MVP |

### 6.2 What ABDM actually is (and is not) [V][S10]
- ABDM is a **health-record exchange network**: ABHA IDs, Health Information Providers (HIP), Health Information Users (HIU), consent artifacts, FHIR records.
- Integration path: sandbox access → build **M1** (ABHA create/verify), **M2** (HIP), **M3** (HIU) → NHA-authorised functional testing + WASA security audit by a CERT-In-empanelled agency → production credentials. Typical timeline **6–9 months** (4–6 if layering onto an existing HMS).
- It is **not** a channel to push ASHA reports into RCH, ANMOL, e-Kavach or BCPM-MIS. The team's "Approach 2: Government API via Ayushman Bharat" (source: a Google AI Mode answer) is therefore unsupported as stated.
- Realistic ABDM role for A.U.R.A.: ABHA verification/linking (M1) as a **roadmap item**; some state ASHA-app specs track "ABHA registered?" per beneficiary for an incentive [U][S25]. Also the "Ayushman Bharat Health Mission" name in the team note is almost certainly **Ayushman Bharat Digital Mission (ABDM)**.

### 6.3 Conclusions that drive the design
1. Do not promise "sync to government portals." Promise "data ready in the exact shape each system needs" and a staged path to official integration.
2. Do not build JS-injection, scraping, or Android-accessibility autofill into government apps: brittle, probably against terms, security-sensitive, and it would put ASHA credentials at risk. (Team "Approach 1: JavaScript workarounds" is rejected.)
3. Pursue official access through NHM/state PMU (questions in `plan.md` §6.3).

---

## 7. Prior art and differentiation [V unless tagged]

| Product | What it is | Overlap | Our difference |
|---|---|---|---|
| ASHABot (Khushi Baby + Microsoft Research) | WhatsApp LLM Q&A bot; Hindi, voice in/out; ~869 ASHAs onboarded in Udaipur (2025) [S20] | Voice-first ASHA UX | It answers questions; it does not capture or report data. |
| KhushiHealth / CHIP (Khushi Baby) | Offline ASHA app + official dashboard; uses GPS/satellite mapping for data-quality accountability [S21] | Offline, ASHA data capture | Uses GPS-based accountability; we explicitly do not. Not voice-structured. |
| AMRIT FLW app (Piramal Swasthya, open source) | Multi-state frontline-worker app with HBNC cards, incentive tracking, U-WIN session logic (seen via public tracker) [S25]; **supports voice entry** (e.g. ABHA generation), Hindi for Bihar, Assamese for Assam [V][S29b] | Incentive logic, visit forms, some voice entry | Form-based with voice for fields; we turn a free spoken note into an evidence-backed whole record reused across outputs. [U — indicative] |
| Wadhwani AI HealthVaani | Hindi/English conversational assistant for health knowledge [S29b] | Voice, Hindi | Q&A, not data capture. |
| Hobby "voice-to-form" builds (e.g. Sakhi: Whisper + Gemma) [S29b] | Single-developer Hindi voice-to-form demos | Very close idea | No published evaluation or pilot; our edge is measured accuracy, evidence spans, privacy contract, reports. |
| e-Kavach (UP) | Government app for UP health functionaries [S13] | The system ASHAs already use | We sit alongside it. |
| mSakhi / ReMiND (UP) | Counselling job aids [S14] | UP ASHA mHealth | Counselling, not documentation. |

Honest positioning: **"no one is doing this" is false.** The defensible gap is *voice → verified structured record → reuse across several outputs, built around the worker's consent and privacy.*

---

## 8. Programme rules reference (inputs to the rule engine)

All rules go in `rules/*.yaml` with a `source` and `status: draft | clinician_reviewed`. **Advisory only; never diagnostic.** A clinician/ANM must review before any real-world use.

### 8.1 HBNC — Home Based Newborn Care [V][S16][S17]
- Institutional delivery: **6 visits** on days **3, 7, 14, 21, 28, 42**.
- Home delivery: **7 visits**, adding **day 1** (within 24 h).
- Extra visits for LBW/preterm/sick newborns (details [U]).
- National incentive ₹250 for the visit series; conditions apply (mother and newborn alive/safe to 42 days; birth registered) [V][S17] (state rate may differ [U]).
- A state tracker spec marks Day 1, 3, 7, 42 as mandatory cards and 14/21/28 as conditional [U][S25] — verify against UP.

### 8.2 HBYC — Home Based care for Young Child [V][S16]
- Visits at **3, 6, 9, 12, 15 months**; national incentive ₹50/visit, ₹250 per child for 5 visits [V][S17].
- Quarterly follow-up of LBW/SNCU-discharged babies is harmonised with HBYC [V].

### 8.3 Universal Immunisation Programme (infants) [V][S18]
| Age | Vaccines |
|---|---|
| Birth (OPV-0 up to 15 days) | BCG, Hep B birth dose (within 24 h), OPV-0 |
| 6 weeks | OPV-1, Penta-1, fIPV-1, Rota-1, PCV-1 |
| 10 weeks | OPV-2, Penta-2, Rota-2 |
| 14 weeks | OPV-3, Penta-3, fIPV-2, Rota-3, PCV-2 |
| 9–12 months | MR-1, JE-1 (where applicable), PCV booster, Vitamin A-1 (fIPV-3 listed by some state sheets) |
| 16–24 months | MR-2, DPT booster-1, OPV booster, JE-2 (where applicable), Vitamin A |
Principle: do not restart a series if a dose is missed; minimum interval 4 weeks between Penta/OPV/Rota doses [V]. State sheets differ slightly (rota/PCV/JE "where applicable") → configure by district.

### 8.4 ANC [V partly][S34]
Minimum **4 ANC visits** + one specialist check under PMSMA (fixed day: **9th of every month**); **up to 3 extra follow-up visits for high-risk pregnancies** under extended PMSMA; ASHA gets ₹100 per HRP mobilised (max 3 follow-ups) [V][S34]. WHO now advises ≥8 contacts; India's guidance remains ≥4 [V][S34]. **Visit-by-visit timing still [U]** → confirm in the MoHFW maternal-health operational guideline before coding ANC tasks (T-013).

### 8.5 ASHA incentives (national; states add their own) [V][S17] — rates must be config, not code
- HBNC ₹250 (6/7 visits); HBYC ₹50 × 5 = ₹250.
- Immunisation session mobilisation: ₹75 per mobiliser, max ₹150 per session site (as read from the annexure snippet; verify context) [V/U]. A state tracker spec uses ₹150 per U-WIN session meeting [U][S25].
- Monthly list preparation (due list, ANC list, eligible-couple list): ₹300 each per month in the annexure; BCG adult due-list ₹300/month × 3 months [V][S17].
- Anaemia Mukt Bharat IFA mobilisation ₹100/month/ASHA [V][S17].
- **UP's current rates and claim form [U]** → obtain (T-005, T-013).

### 8.6 Records ASHAs keep [V][S26]
Village Health Register (≈96% had it in one study), delivery forms, home-visit form, ASHA diary (≈28%), drug-kit stock register, birth-preparedness plan, newborn examination format. Registers are meant to be updated monthly (due lists etc.).

### 8.7 Reporting cadence
Monthly is supported (HMIS by the 10th; ASHA incentive claims monthly) [V]. **Weekly is not established** → answer to the team's open question: build monthly first.

---

## 9. Technology facts

### 9.1 Speech-to-text options [V]
| Option | Facts | Notes |
|---|---|---|
| **Bhashini / Dhruva pipeline** | Gov platform; register to get ULCA `userID` + API key; pipeline inference endpoint; AI4Bharat multilingual conformer service available [S7] | Rate limits/ToS [U]. Gov-aligned, good for the pitch. |
| **Sarvam Saaras v3** | 22 Indian languages + English; code-mixing; REST for **< 30 s** audio, Batch API for longer; streaming via WebSocket [S4]. **₹30 per hour of audio**, billed per second [S5] | Saarika v2.5 is legacy (to be deprecated). Data residency/retention [U]. |
| **AI4Bharat IndicConformer** (self-host) | Open ASR; 600M multilingual model covers 22 languages (HF); monolingual large models per language; GitHub states MIT, some HF repos show CC-BY-4.0 [S6] | Check license per model before shipping [U]. Needs AI4Bharat NeMo or ONNX path. |
| **IndicWhisper** | Whisper fine-tuned on Vistaar; best WER on 39 of 59 benchmarks (2023) [S8] | Evaluate; check license. |
| **On-device (sherpa-onnx)** | Community conversions of IndicConformer to sherpa-onnx packs (~175 MB, CC-BY-4.0) run offline on a 3 GB Android phone; error rates reported only on synthetic speech [S9]. Flutter wrappers exist (`sherpa_onnx`, `sherpa_asr_sdk`) | Stretch goal, not MVP. |
| **Single-pass multimodal LLM** (audio → JSON) | Candidate baseline that removes the STT→LLM error chain | Test in bake-off; residency/cost [U]. |

### 9.1a Updates from research pass 2 (2026-10-28)
- **Sarvam:** STT ₹30/hour (diarization reportedly ₹45/h [U]); REST ≤30 s, Batch ≤2 h/file, WebSocket streaming; a v4 realtime model is GA (pricing [U]); developer page states zero data retention by default and no training on API inputs [V as a vendor claim][S29]. Concurrency limits per plan [U].
- **Bhashini:** still two-step (pipeline config with ULCA userID + API key → Dhruva inference); WebSocket ASR documented; current Hindi pipeline ID [U] [S7][S29].
- **IndicConformer-600M multilingual:** MIT (GitHub + HF card) but **gated download** (accept terms on HF); no official ONNX; community int8 ONNX exists [V][S31]. Closes U15 for this model.
- **LLM candidates (Claude, list prices per 1M tokens in/out):** `claude-haiku-5-5` $0.10/$0.50, `claude-sonnet-5-5` $2/$10, `claude-opus-5-5` $4/$20; structured JSON output via `output_config.format` [V][S32]. Data residency for India [U].
- **Flutter `record`:** supports WAV/PCM16; actual sample rate depends on OS settings; open issues on silent WAV failures on some Android devices [V][S33].

### 9.2 Accuracy reality [V][S8]
2023 Vistaar (Hindi): IndicWhisper averages **13.6% WER**, NVIDIA conformers **18.6–19.4%**; the hardest Hindi subset (likely the telephone-quality, dialectal set — column label not confirmed) ran **26.8–42.6%**. 2026 update: Vaani Benchmark v1.0 (20.6 h spontaneous Hindi, 104 districts) reports best WER Vaani Fast Conformer 10.6%, Gemini-3.1-Pro 11.9%, Sarvam Saaras v3 13.7%, IndicConformer-600M close behind; Whisper-large-v3 and GPT-4o-Transcribe much worse; rankings differ across benchmarks [V][S30]. Standard WER over-penalises valid Hindi script/nukta variants → normalise before scoring [V][S30]. Field audio from rural UP (Awadhi/Bhojpuri-influenced Hindi, noise, cheap mics, Hindi–English code-mix like "BP", "Hb", "TT") will sit closer to the hard end. Newer models should be better, but **assume 15–30% WER on real field audio until measured**. Hence: the confirm step is the core of the product, not a nicety, and the numbers on our slides must come from our own test set.

### 9.3 Offline-first [V][S28]
- Recommended local DB: **drift (SQLite) + SQLCipher** (`sqlcipher_flutter_libs`). Own the sync (simple outbox + idempotent push + pull-since-cursor).
- Packages `relax_orm` and `dart_data` offer sync/encryption but are v0.1.x with minimal adoption → treat as reference, not dependencies.
- Sarvam REST limit (< 30 s) → cap each spoken segment at 30 s or use Batch.

### 9.4 Backend [D]
FastAPI + PostgreSQL; provider adapters for STT and LLM; API keys only on the server; India-region hosting preferred.

### 9.5 Unit economics (assumption-based, for the "cost" criterion) [U]
STT at ₹30/hour. Example: 5 visits/day × 45 s × 26 days ≈ 1.6 h audio/month ≈ **₹49 per ASHA per month** for STT. For 1,000 ASHAs ≈ ₹49,000/month; for UP's ~1.6 lakh ≈ ₹78 lakh/month before discounts or self-hosting. LLM cost to be measured in the bake-off (Sarvam LLM pricing pages conflict: "free" vs ₹4/₹2.5/₹16 per 1M tokens [U]). Self-hosted/Bhashini routes reduce this. State the assumptions on any slide.

---

## 10. Law, privacy, ethics (not legal advice)

- **DPDP Act 2023 + DPDP Rules 2025** (notified 13/14 Nov 2025) [V][S19]. Phased enforcement dates: **14 Nov 2025**, **14 Nov 2026** (consent-manager provisions), **14 May 2027** (main fiduciary obligations) per law-firm summaries; confirm in the Gazette [V/U].
- Key obligations to design for now: itemised notice and consent, purpose limitation, retention limits, reasonable security safeguards, **breach notification (72 h)**, grievance redressal, children's data needs verifiable parental consent with class exemptions for certain fiduciaries such as healthcare providers [V][S19].
- Roles: beneficiary data belongs to the health system. NHM/state is realistically the **data fiduciary**; A.U.R.A. would be a **processor** acting on its behalf. If an ASHA stores beneficiary data in an unofficial app, someone must be accountable; resolve with NHM before any pilot [U].
- ABDM adds the Health Data Management Policy and security audit requirements if we ever integrate [V][S10].
- **Prototype rule: synthetic data only. No real beneficiary names, no real recordings of patients.** Voice samples come from team members/consenting volunteers reading scripts.
- Data minimisation: audio deleted after confirmation (hard cap 7 days) [D].
- **Worker-first privacy contract (product requirement):** no location/GPS permission, no contacts/call log/SMS, no screen or other-app monitoring, no attendance, no per-worker productivity scoring or time-of-day activity analytics. Permissions: microphone (+ notifications). The ASHA can export and delete her data.
- Voice data leaving the device goes to a third-party STT/LLM: inform in-app, prefer India-hosted/government services.

---

## 11. Glossary

ASHA: Accredited Social Health Activist. ANM: Auxiliary Nurse Midwife. AWW: Anganwadi Worker. ASHA Sangini/Facilitator: ASHA supervisor. BCPM/BAM: Block Community Process Manager / Block Accounts Manager. NHM: National Health Mission. ANC/PNC: ante/post-natal care. HBNC/HBYC: Home Based Newborn / Young Child Care. VHND: Village Health & Nutrition Day. VHSNC: Village Health, Sanitation & Nutrition Committee. LBW: low birth weight. SNCU/NRC: special newborn care unit / nutrition rehabilitation centre. UIP: Universal Immunisation Programme. RCH: Reproductive and Child Health portal. ANMOL: ANM Online. U-WIN: universal immunisation registry. HMIS: Health Management Information System. ABDM: Ayushman Bharat Digital Mission. ABHA: Ayushman Bharat Health Account ID. HIP/HIU: health information provider/user. PMSMA: Pradhan Mantri Surakshit Matritva Abhiyan (9th of month ANC). DPDP: Digital Personal Data Protection. STT/TTS: speech-to-text / text-to-speech. WER: word error rate. SFIC: Seva First Innovation Challenge.

---

## 12. Unverified-claims register [U]

| # | Item | How to close |
|---|---|---|
| U1 | Origin of the "16%" figure | Remove or measure (T-011, T-014) |
| U2 | "ASHAs on strike across India through 2026" | Verify with news sources |
| U3 | Kerala 2025 numbers | Cite or drop |
| U4 | POC results | Run eval (E2) |
| U5 | Any ABDM route to RCH/ANMOL/e-Kavach/BCPM | Ask NHM/NHA (T-012) |
| U6 | Third-party API availability: U-WIN, e-Kavach, BCPM-MIS, Nikshay | Ask NHM (T-012) |
| U7 | UP incentive rates + BCPM claim workflow + claim form | Obtain forms/interview (T-005, T-010) |
| U8 | ANC schedule per MoHFW | Verify (T-013) |
| U9 | Bhashini rate limits/ToS | Register and read (T-023) |
| U10 | Sarvam LLM pricing conflict; STT data residency/retention | Read terms (T-023) |
| U11 | "ASHA-Nidhi" on architecture slide | Confirm name/existence |
| U12 | SFIC final deadline, finale venue, prize basis | Portal (T-001) |
| U13 | UP ASHA device profile (OS, RAM, mic) | Interviews (T-010) |
| U14 | Hindi dialect ASR performance in UP | Eval (E2) |
| U15 | IndicConformer license per model — 600M multilingual closed (MIT, gated); others open | Read model cards (T-023) |
| U16 | EnVision Phase 2 internal deadline | Ask coordinator |
| U17 | Whether UP ASHAs enter visit data in e-Kavach or ANMs do | Interviews (T-010) |
| U18 | Weekly reporting need | Interviews (T-010) |
| U19 | AMRIT FLW overlap details | Read the open-source repo/docs |
| U20 | Team skills and availability | Skills matrix (T-002) |

---

## 13. Sources

- [S1] SFIC portal home — https://sevafirst.mic.gov.in/
- [S2] SFIC timeline — https://sevafirst.mic.gov.in/timeline
- [S3] LICET email "Envision 2026 – Seva First Innovation Challenge", 1 Oct 2026 (team-provided PDF)
- [S4] Sarvam STT docs — https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe.md ; overview https://docs.sarvam.ai/api-reference-docs/speech-to-text/apis/overview
- [S5] Sarvam pricing — https://docs.sarvam.ai/api/getting-started/pricing
- [S6] AI4Bharat IndicConformer — https://github.com/AI4Bharat/IndicConformerASR ; https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
- [S7] Bhashini Dhruva client examples — https://pypi.org/project/bhashini-client/ ; https://huggingface.co/spaces/pvanand/web-server/blob/d6ef585eb7fe48647e72e08ab1b766a636a5eb2c/ai4b.py
- [S8] Vistaar (Interspeech 2023) — https://arxiv.org/abs/2305.15386 ; https://github.com/AI4Bharat/vistaar
- [S9] Offline Indic sherpa-onnx packs — https://huggingface.co/datasets/Mr66/itantra-packs ; https://pub.dev/packages/sherpa_asr_sdk
- [S10] ABDM milestones/certification — https://qualysec.com/abdm-integration-checklist/ ; https://nirmitee.io/blog/abdm-certification-process-sandbox-to-production-guide/ ; https://devforum.abdm.gov.in/ ; https://github.com/dimagi/abdm-python-integrator
- [S11] MoHFW brief on MCTS/RCH/ANMOL — https://main.mohfw.gov.in/sites/default/files/MMPC%20Brief.pdf
- [S12] RCH/ANMOL — https://wcd.nic.in/poshan/Events/TechThon/ExistingTechnologyPlatform_for_HealthSchemes_MoHFW-28-06-2018.pdf ; https://anantamias.com/rch-portal/ ; https://exint.rmnch.mohfw.gov.in/privacypolicy.html
- [S13] e-Kavach — https://ekavach.upnrhm.gov.in/imtecho-ui/privacyPolicy.html ; https://argusoft.com/medplat/eKavach.html ; Amar Ujala Basti, 4 Aug 2026
- [S14] UP Digital ASHA Payment / BCPM MIS (Vikaspedia) — https://en.vikaspedia.in/health/health-care-innovations/good--replicable-and-innovative-practices/digital-asha-payment
- [S15] Parliament replies on ASHAs — https://eparlib.nic.in/bitstream/123456789/2973780/1/AS12.pdf ; https://eparlib.sansad.in/bitstream/123456789/3014854/1/AU4639_yPE0iU.pdf
- [S16] HBNC/HBYC portal — https://hbnc-hbyc.mohfw.gov.in/about ; https://hbnc-hbyc.mohfw.gov.in/AboutUs/aboutHBNC ; HBYC job aid PDF on the same portal
- [S17] NHM ASHA incentives — https://nhm.gov.in/New-update-2024-25/ASHA/ASHA-Incentives-July-2025.pdf ; https://www.nhm.gov.in/New-Update-2025-26/ASHA-incentive/ASHA%20Incentives.pdf
- [S18] National Immunization Schedule — https://main.mohfw.gov.in/sites/default/files/Unit2NationalImmunizationSchedule.pdf
- [S19] DPDP Rules 2025 — https://www.scconline.com/blog/post/2025/11/14/meity-notified-digital-personal-data-protection-rules-2025/ ; https://www.amsshardul.com/wp-content/uploads/2025/11/Regulatory-Alert-Enforcement-of-DPDP-Act-and-Notification-of-DPDP-Rules.pdf ; https://www.ey.com/en_in/insights/cybersecurity/transforming-data-privacy-digital-personal-data-protection-rules-2025
- [S20] ASHABot — https://arxiv.org/html/2409.10913v3 ; https://www.georgeinstitute.org/news-and-media/news/building-ai-solutions-based-on-essential-needs-not-just-hype-part-2 ; https://www.microsoft.com/en-us/research/?p=1141120
- [S21] KhushiHealth — https://solve.mit.edu/solutions/28855
- [S22] Surveillance/double work — https://www.codastory.com/?p=23039 ; https://behanbox.com/?p=16697 ; https://newlinesmag.com/reportage/indias-digital-health-push-is-overworking-its-front-line-women/
- [S23] Time use — https://nmji.in/nmji/archives/Volume-23/Issue-3/PDF-volume-23-issue-3/Original-Article-II.pdf ; https://ideas.repec.org/a/eee/socmed/v382y2025ics0277953625007014.html
- [S24] U-WIN / Co-WIN API model — https://covid19dashboard.mohfw.gov.in/pdf/CoWINAPIGuidelinesFinal240521.pdf ; https://www.tribuneindia.com/news/health/after-co-win-govt-launches-u-win-to-digitise-indias-universal-immunisation-programme-473039
- [S25] Piramal Swasthya AMRIT FLW public tracker (indicative) — https://support.piramalfoundation.org/jira/browse/FLW-340 ; .../FLW-323 ; .../AMM-1872 ; .../FLW-512
- [S26] ASHA records/HBNC formats — https://www.indianpediatrics.net/feb2014/feb-142-144.htm ; https://journals.innovareacademics.in/index.php/ajpcr/article/download/45976/27280 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC8279773/table/pone.0252700.t003
- [S27] HMIS monthly by the 10th — https://nhm.assam.gov.in/sites/default/files/swf_utility_folder/departments/nhm_lipl_in_oid_6/menu/document/guidelines_and_district_rop_2022-24_mis_0.pdf
- [S28] Flutter offline/sync packages — https://pub.dev/packages/relax_orm ; https://pub.dev/packages/dart_data
- [S29] Sarvam docs/pricing/developers (fetched 2026-10-28) — https://sarvam.ai/api-pricing ; https://docs.sarvam.ai/api-reference-docs/getting-started/models/saaras.md ; https://sarvam.ai/developers ; Bhashini WebSocket ASR — https://dibd-bhashini.gitbook.io/bhashini-apis/websocket-asr-api ; Glific Bhashini guide — https://glific.github.io/docs/docs/Integrations/Bhashini%20ASR
- [S29b] Competitor scan 2026 — https://amrit.pages.dev/products/front-line-worker-app ; https://www.wadhwaniai.org/impact/healthcare-solutions/healthvaani/ ; https://pulseaugur.com/cluster/39122
- [S30] Vaani Benchmark v1.0 (June 2026) — https://arxiv.org/pdf/2606.21408 ; Voice of India benchmark — https://voiceofindiablogs.ai.joshtalks.com/
- [S31] IndicConformer-600M HF card — https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual ; community int8 ONNX — https://huggingface.co/yashwork-byte/indic-conformer-600m-int8-onnx
- [S32] Anthropic Claude API model table and pricing (claude-api skill, cached 2026-10-06; confirm live before quoting)
- [S33] Flutter `record` package — https://pub.dev/documentation/record/5.2.1 ; https://docs.flutter.dev/cookbook/audio/record
- [S34] ANC / PMSMA — https://eparlib.sansad.in/bitstream/123456789/2983672/1/AS66_pXAnrP.pdf ; https://nhm.gov.in/images/pdf/programmes/maternal-health/guidelines/Pradhan_Mantri_Surakshit_Matritva_Abhiyan.pdf ; https://bmcpregnancychildbirth.biomedcentral.com/counter/pdf/10.1186/s12884-023-06117-z.pdf

Team-provided documents: Envision '26 deck; Home/Data-Entry/Report/Settings workflow PDF; "Team Research Compilation" (UP focus).
