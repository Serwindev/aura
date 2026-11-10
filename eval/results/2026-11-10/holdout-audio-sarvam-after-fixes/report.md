# Eval report — notes_holdout — 2026-11-10

> **Read this first.** Synthetic notes written by the same developer (Claude) who wrote the
> rule-based extractor, **spoken by an AI voice** (AI voice (Sarvam bulbul:v3 TTS), not field speech), then transcribed by `sarvam-saaras-v4`.
> AI voices are clean: this tests the audio path end to end, **not field accuracy**. Do not
> put these numbers on a slide without this caveat.

- Extractor: `rule-based-v0` (deterministic, offline) · STT: sarvam-saaras-v4
- Machine: Windows 11, Python 3.12.10

## Headline

| Metric | Value |
|---|---|
| Field precision / recall / F1 (micro, 104 TP · 2 FP · 12 FN) | 0.98 / 0.90 / 0.94 |
| Notes with every critical field right | 0.90 (18/20) |
| Unsupported values (filled where gold says nothing was said) | 0.000 |
| Text pipeline latency p50 / p95 (extract + validate + names) | 12.9 / 19.2 ms |
| Mean error flags per note (shown to the ASHA for review) | 0.10 |
| STT word error rate (raw: no number/spelling normalisation) / STT time p50, max | 0.128 / 0.6 s, 1.5 s |
| LLM extractor | **not measured** (no API key) |

## By transcript style

| Style | P | R | F1 |
|---|---|---|---|
| stt | 1.00 | 0.91 | 0.95 |
| clean | 0.96 | 0.89 | 0.92 |

## Per field

| Field | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|
| visit_type | 19 | 0 | 1 | 1.00 | 0.95 | 0.97 |
| visit_date | 20 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| beneficiary_id | 19 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hbnc_day | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hbyc_month | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| anc_number | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| weight_kg | 10 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| temp_c | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_sys | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_dia | 1 | 0 | 1 | 1.00 | 0.50 | 0.67 |
| hb_g_dl | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| resp_rate | 0 | 0 | 1 | n/a | 0.00 | n/a |
| referral_needed | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| referral_facility | 3 | 1 | 1 | 0.75 | 0.75 | 0.75 |
| danger_signs | 8 | 0 | 2 | 1.00 | 0.80 | 0.89 |
| services | 7 | 1 | 5 | 0.88 | 0.58 | 0.70 |
| next_due | 0 | 0 | 1 | n/a | 0.00 | n/a |

## Notes with errors

| Note | Style | Tags | Wrong fields |
|---|---|---|---|
| h02 | clean |  | danger_signs |
| h04 | clean |  | danger_signs, resp_rate |
| h08 | clean |  | services |
| h10 | clean |  | services |
| h11 | stt |  | next_due |
| h13 | stt |  | bp_dia |
| h16 | clean |  | referral_facility |
| h17 | stt |  | services |
| h19 | stt |  | visit_type |

## What was said vs heard

| Note | Said | Heard |
|---|---|---|
| h01 | सुनीता की बेटी को आज देखा तीसरा दिन है वजन दो किलो सात सौ ग्राम बच्ची ठीक से दूध पी रही है | सुनीता की बेटी को आज देखा तीसरा दिन है। वज़न दो किलो सात सौ ग्राम बच्ची ठीक से दूध पी रही है। |
| h02 | रेखा के बेटे का 14वें दिन का HBNC विज़िट आज किया। वज़न 3 किलो 200 ग्राम। नाभि में लाली नहीं है। | रेखा के बेटे का चौदहवें दिन का एचबीएनसी विजिट आज किया। वजन तीन किलो दो सौ ग्राम। नाभि में लाली नहीं है। |
| h03 | अनीता के बच्चे को बहुत तेज़ बुखार है एक सौ दो डिग्री दूध भी नहीं पी रहा एचबीएनसी विजिट आज किया एसएनसीयू रेफर किया | अनीता के बच्चे को बहुत तेज़ बुखार है। 102 डिग्री, दूध भी नहीं पी रहा। एचबीएनसी विज़िट आज किया, एसएनसीयू रेफर किया। |
| h04 | Today did HBNC visit day 7 for Rekha's baby. Weight 2.95 kg. Breathing fast, around 70 per minute. Referred to CHC. | Today did Hbnc visit day 7 for Rekha's baby. Weight 2.95 kilogram. Breathing fast, around 70 per minute. Refer to CHC. |
| h05 | ममता के बच्चे का अट्ठाईसवें दिन का एचबीएनसी विजिट किया वजन तीन किलो आठ सौ ग्राम सब ठीक है | ममता के बच्चे का अट्ठाईसवें दिन का एचबीएनसी विज़िट किया। वज़न तीन किलो आठ सौ ग्राम, सब ठीक है। |
| h06 | आज आरव का HBYC विज़िट हुआ, उम्र 9 महीने। वज़न 8.2 किलो। बच्चे को दस्त है और पानी की कमी लग रही है। ORS दिया। | आज आरव का एचबीवाईसी विज़िट हुआ। उम्र नौ महीने, वज़न 8.2 किलो। बच्चे को दस्त है और पानी की कमी लग रही है। ओआरएस दिया। |
| h07 | प्रिया का एचबीवाईसी छठे महीने का विजिट आज वजन छह किलो पांच सौ ग्राम बच्ची को खांसी है | प्रिया का एचबीवाईसी छठे महीने का विज़िट। आज वज़न 6 किलो 500 ग्राम, बच्ची को खांसी है। |
| h08 | ईशान को आज MR-2 और DPT booster लगाया। | ईशान को आज एमआर2 और डीपीटी बूस्टर लगाया। |
| h09 | अनन्या को आज रोटा का तीसरा टीका और पेंटा तीन लगाया | अनन्या को आज रोटा का तीसरा टीका और पेंटा तीन लगाया। |
| h10 | आयान का टीकाकरण कल हुआ - OPV 1 और Penta 1 दिए गए। | आयान का टीकाकरण कल हुआ। ओ.पी.वी. एक और पेंटा एक दिए गए। |
| h11 | आज शबनम के बच्चे को टीका नहीं लग पाया टीका केंद्र पर वैक्सीन खत्म था शुक्रवार को फिर लगेगा | आज शबनम के बच्चे को टीका नहीं लग पाया। टीका केंद्र पर वैक्सीन खत्म था। शुक्रवार को फिर लगेगा। |
| h12 | पूजा यादव की चौथी ANC जांच आज। BP 130/85, वज़न 60 किलो, Hb 9 g/dl। पैरों में हल्की सूजन है। | पूजा यादव की चौथी एएनसी जांच आज। बीपी 130/85, वज़न 60 किलो, एचबी 9 जी/डीएल। पैरों में हल्की सूजन है। |
| h13 | गीता का बीपी एक सौ पचास बाई सौ है आँखों के आगे धुंधला दिखता है एएनसी विजिट आज किया तुरंत जिला अस्पताल रेफर किया | गीता का बीपी 150/200 है। आँखों के आगे धुंधला दिखता है। एएनसी विजिट आज किया, तुरंत जिला अस्पताल रेफर किया। |
| h14 | Sarita ki ANC visit today. Haemoglobin 8.9, weight 57 kg. Calcium and IFA given. | Sarita Ki ANC Visit Today, Hemoglobin 8.9, Weight 57 kg, Calcium And IFA Given. |
| h15 | आज गर्भवती पूजा के घर गई बच्चे की हलचल ठीक है वजन पचपन किलो आयरन की गोलियां दीं | आज गर्भवती पूजा के घर गए बच्चे की हलचल ठीक है। वज़न 55 किलो, आयरन की गोलियाँ दीं। |
| h16 | आज सुनीता देवी की PNC विज़िट। बहुत ज़्यादा खून आ रहा है, CHC भेजा। | आज सुनीता देवी की पीएनसी विजिट। बहुत ज्यादा खून आ रहा है। सीएचसी भेजा। |
| h17 | ममता के घर गई परिवार नियोजन पर बात की अंतरा का इंजेक्शन लगाया | ममता के घर गए परिवार नियोजन पर बात की अंतरा का इंजेक्शन लगाया। |
| h18 | रमेश जी की टीबी दवा का फॉलो-अप, कल किया। दवा ठीक से ले रहे हैं। | रमेश जी की टीबी दवा का फॉलोअप कल किया। दवा ठीक से ले रहे हैं। |
| h19 | हमने आज कविता के बेटे आरव को देखा उसको तेज़ साँस चल रही है छाती अंदर धँस रही है | हमने आज कविता के बेटे आरव को देखा। उसको तेज़ साँस चल रही है, छाती अंदर धँस रही है। |
| h20 | राधा के बेटे का HBYC 15 महीने वाला विज़िट परसों हुआ, वज़न 10.4 किलो। | राधा के बेटे का एचबीवाईसी पंद्रह महीने वाला विज़िट परसों हुआ। वज़न 10.4 किलो। |

Raw per-note predictions vs gold: `results.json`.
