# Eval report — notes_holdout — 2026-11-10

> **Read this first.** Synthetic notes written by the same developer (Claude) who wrote the
> rule-based extractor, **spoken by an AI voice** (AI voice (Sarvam bulbul:v3 TTS), not field speech), then transcribed by `vosk-small-hi-0.22`.
> AI voices are clean: this tests the audio path end to end, **not field accuracy**. Do not
> put these numbers on a slide without this caveat.

- Extractor: `rule-based-v0` (deterministic, offline) · STT: vosk-small-hi-0.22
- Machine: Windows 11, Python 3.12.10

## Headline

| Metric | Value |
|---|---|
| Field precision / recall / F1 (micro, 65 TP · 4 FP · 51 FN) | 0.94 / 0.56 / 0.70 |
| Notes with every critical field right | 0.30 (6/20) |
| Unsupported values (filled where gold says nothing was said) | 0.000 |
| Text pipeline latency p50 / p95 (extract + validate + names) | 11.7 / 17.8 ms |
| Mean error flags per note (shown to the ASHA for review) | 0.50 |
| STT word error rate (raw: no number/spelling normalisation) / STT time p50, max | 0.344 / 1.7 s, 2.6 s |
| LLM extractor | **not measured** (no API key) |

## By transcript style

| Style | P | R | F1 |
|---|---|---|---|
| stt | 0.97 | 0.71 | 0.82 |
| clean | 0.90 | 0.43 | 0.58 |

## Per field

| Field | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|
| visit_type | 10 | 0 | 10 | 1.00 | 0.50 | 0.67 |
| visit_date | 19 | 1 | 1 | 0.95 | 0.95 | 0.95 |
| beneficiary_id | 13 | 1 | 6 | 0.93 | 0.68 | 0.79 |
| hbnc_day | 0 | 0 | 4 | n/a | 0.00 | n/a |
| hbyc_month | 0 | 0 | 3 | n/a | 0.00 | n/a |
| anc_number | 0 | 0 | 1 | n/a | 0.00 | n/a |
| weight_kg | 8 | 0 | 2 | 1.00 | 0.80 | 0.89 |
| temp_c | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_sys | 0 | 0 | 2 | n/a | 0.00 | n/a |
| bp_dia | 0 | 0 | 2 | n/a | 0.00 | n/a |
| hb_g_dl | 0 | 0 | 2 | n/a | 0.00 | n/a |
| resp_rate | 0 | 0 | 1 | n/a | 0.00 | n/a |
| referral_needed | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| referral_facility | 2 | 1 | 2 | 0.67 | 0.50 | 0.57 |
| danger_signs | 6 | 0 | 4 | 1.00 | 0.60 | 0.75 |
| services | 2 | 1 | 10 | 0.67 | 0.17 | 0.27 |
| next_due | 0 | 0 | 1 | n/a | 0.00 | n/a |

## Notes with errors

| Note | Style | Tags | Wrong fields |
|---|---|---|---|
| h01 | stt |  | beneficiary_id, hbnc_day, visit_type |
| h02 | clean |  | danger_signs, hbnc_day |
| h03 | stt |  | danger_signs |
| h04 | clean |  | beneficiary_id, danger_signs, hbnc_day, referral_facility, resp_rate, visit_type, weight_kg |
| h05 | stt |  | hbnc_day |
| h06 | clean |  | beneficiary_id, danger_signs, hbyc_month, services, visit_type |
| h07 | stt |  | hbyc_month, visit_type |
| h08 | clean |  | beneficiary_id, services |
| h09 | stt |  | services |
| h10 | clean |  | beneficiary_id, services, visit_date |
| h11 | stt |  | next_due |
| h12 | clean |  | anc_number, bp_dia, bp_sys, hb_g_dl, visit_type |
| h13 | stt |  | bp_dia, bp_sys, visit_type |
| h14 | clean |  | beneficiary_id, hb_g_dl, services, visit_type, weight_kg |
| h16 | clean |  | referral_facility, visit_type |
| h17 | stt |  | services |
| h19 | stt |  | visit_type |
| h20 | clean |  | hbyc_month, visit_type |

## What was said vs heard

| Note | Said | Heard |
|---|---|---|
| h01 | सुनीता की बेटी को आज देखा तीसरा दिन है वजन दो किलो सात सौ ग्राम बच्ची ठीक से दूध पी रही है | सुनीता जी बेटी को देखा तीसरा दिन है वजन दो किलो सात सौ ग्राम बच्ची ठीक से दूध पी रही है |
| h02 | रेखा के बेटे का 14वें दिन का HBNC विज़िट आज किया। वज़न 3 किलो 200 ग्राम। नाभि में लाली नहीं है। | रेखा के बेटे का चौदह दिन का एचपीएमसी विजेट आज गया वजन तीन किलो दो सौ ग्राम नाभि में लाली नहीं है |
| h03 | अनीता के बच्चे को बहुत तेज़ बुखार है एक सौ दो डिग्री दूध भी नहीं पी रहा एचबीएनसी विजिट आज किया एसएनसीयू रेफर किया | अनीता के बच्चे को बहुत तेज बुखार है एक सौ दो डिग्री दूध भी नहीं पी रहा एचपीएमसी विजेता आज किया एसएनसीयू रेफर किया |
| h04 | Today did HBNC visit day 7 for Rekha's baby. Weight 2.95 kg. Breathing fast, around 70 per minute. Referred to CHC. | cody did is be unseen dares seven for it has barely v two point nine five children breathing fast are on seventy per minute refer to see at sea |
| h05 | ममता के बच्चे का अट्ठाईसवें दिन का एचबीएनसी विजिट किया वजन तीन किलो आठ सौ ग्राम सब ठीक है | ममता के बच्चे का अट्ठाईस वें दिन का एच बी सी विजिट किया वजन तीन किलो आठ सौ ग्राम सब ठीक है |
| h06 | आज आरव का HBYC विज़िट हुआ, उम्र 9 महीने। वज़न 8.2 किलो। बच्चे को दस्त है और पानी की कमी लग रही है। ORS दिया। | आज का एच बी वाई सी विजिट हुआ उम्र नौ महीने वजन आठ प्वाइंट दो किलो बच्चे को दस्त है और पानी की कमी लग रही है और इस दिया |
| h07 | प्रिया का एचबीवाईसी छठे महीने का विजिट आज वजन छह किलो पांच सौ ग्राम बच्ची को खांसी है | प्रिया का एच बी वाई सी छठे महीने का विजेट आज वजन छः किलो पाँच सौ ग्राम बच्ची को खांसी है |
| h08 | ईशान को आज MR-2 और DPT booster लगाया। | शाम को आज एम आर टू और डीपीटी बूस्ट लगाया |
| h09 | अनन्या को आज रोटा का तीसरा टीका और पेंटा तीन लगाया | अनन्या को आज रोता का तीसरा टीका और टेंडर तीन लगाया |
| h10 | आयान का टीकाकरण कल हुआ - OPV 1 और Penta 1 दिए गए। | आयाम का टीकाकरण हुआ ओपीवी एक और पेंट एक दिए गए |
| h11 | आज शबनम के बच्चे को टीका नहीं लग पाया टीका केंद्र पर वैक्सीन खत्म था शुक्रवार को फिर लगेगा | आज शबनम के बच्चे को टीका नहीं लगवाया टीका केंद्र पर वैक्सीन खत्म था शुक्रवार को फिर लगेगा |
| h12 | पूजा यादव की चौथी ANC जांच आज। BP 130/85, वज़न 60 किलो, Hb 9 g/dl। पैरों में हल्की सूजन है। | पूजा यादव की चौथी एमसी जांच आज बीपी एक सौ तीस पचासी वजन साठ किलो बीज भी न होगी बायोडीजल पैरों में हल्की सूजन है |
| h13 | गीता का बीपी एक सौ पचास बाई सौ है आँखों के आगे धुंधला दिखता है एएनसी विजिट आज किया तुरंत जिला अस्पताल रेफर किया | गीता का बीपी एक सौ पचास बाई सो है आंखों के आगे धुँधला दिखता है एजेंसी विजिट आज किया तुरंत जिला अस्पताल रेफर किया |
| h14 | Sarita ki ANC visit today. Haemoglobin 8.9, weight 57 kg. Calcium and IFA given. | surrey tacky and civic rare immortal or been aired point nine vet fifty seven kilogram kelsey amend men are forgiven |
| h15 | आज गर्भवती पूजा के घर गई बच्चे की हलचल ठीक है वजन पचपन किलो आयरन की गोलियां दीं | आज गर्भवती पूजा के घर के बच्चे की हलचल ठीक है वजन पचपन किलो आयरन की गोलियां दी |
| h16 | आज सुनीता देवी की PNC विज़िट। बहुत ज़्यादा खून आ रहा है, CHC भेजा। | आज सुनीता देवी की पीएमसी बजट बहुत ज्यादा खून आ रहा है सीएचसी भेजा |
| h17 | ममता के घर गई परिवार नियोजन पर बात की अंतरा का इंजेक्शन लगाया | ममता जी घर परिवार नियोजन पर बाद की अंतरा का इंजेक्शन लगाया |
| h18 | रमेश जी की टीबी दवा का फॉलो-अप, कल किया। दवा ठीक से ले रहे हैं। | रमेश जी की टीबी दवा का फॉलोअप कल किया दवा ठीक से ले रहे हैं |
| h19 | हमने आज कविता के बेटे आरव को देखा उसको तेज़ साँस चल रही है छाती अंदर धँस रही है | हमने आज कविता के बेटे आरव को देखा उसको तेज सांस चल रही है छाती अंदर धंस रही है |
| h20 | राधा के बेटे का HBYC 15 महीने वाला विज़िट परसों हुआ, वज़न 10.4 किलो। | राधा के बेटे का एच बी वाई सी पंद्रह महीने वाला विजेट परसों हुआ वजन दस प्वाइंट चार किलो |

Raw per-note predictions vs gold: `results.json`.
