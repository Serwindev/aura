# Eval report — notes_holdout — 2026-11-09

> **Read this first.** 40 *synthetic, text-only* notes written by the same developer (Claude) who
> wrote the rule-based extractor. This is a **smoke test of the pipeline**, not evidence of
> real-world accuracy. No audio was recorded, so speech-to-text error (WER/CER) is **not measured**.
> Do not put these numbers on a slide without this caveat.

- Extractor: `rule-based-v0` (deterministic, offline) · STT: none (text transcripts)
- Machine: Windows 11, Python 3.12.10

## Headline

| Metric | Value |
|---|---|
| Field precision / recall / F1 (micro, 104 TP · 1 FP · 12 FN) | 0.99 / 0.90 / 0.94 |
| Notes with every critical field right | 0.85 (17/20) |
| Unsupported values (filled where gold says nothing was said) | 0.000 |
| Text pipeline latency p50 / p95 (extract + validate + names) | 10.1 / 14.7 ms |
| Mean error flags per note (shown to the ASHA for review) | 0.10 |
| STT WER / CER | **not measured** (no recordings) |
| LLM extractor | **not measured** (no API key) |

## By transcript style

| Style | P | R | F1 |
|---|---|---|---|
| stt | 1.00 | 0.87 | 0.93 |
| clean | 0.98 | 0.92 | 0.95 |

## Per field

| Field | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|
| visit_type | 18 | 0 | 2 | 1.00 | 0.90 | 0.95 |
| visit_date | 20 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| beneficiary_id | 19 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hbnc_day | 3 | 0 | 1 | 1.00 | 0.75 | 0.86 |
| hbyc_month | 2 | 0 | 1 | 1.00 | 0.67 | 0.80 |
| anc_number | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| weight_kg | 10 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| temp_c | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_sys | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_dia | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hb_g_dl | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| resp_rate | 0 | 0 | 1 | n/a | 0.00 | n/a |
| referral_needed | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| referral_facility | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| danger_signs | 7 | 0 | 3 | 1.00 | 0.70 | 0.82 |
| services | 9 | 1 | 3 | 0.90 | 0.75 | 0.82 |
| next_due | 0 | 0 | 1 | n/a | 0.00 | n/a |

## Notes with errors

| Note | Style | Tags | Wrong fields |
|---|---|---|---|
| h01 | stt |  | hbnc_day, visit_type |
| h02 | clean |  | danger_signs |
| h03 | stt |  | danger_signs |
| h04 | clean |  | danger_signs, resp_rate |
| h06 | clean |  | hbyc_month |
| h08 | clean |  | services |
| h11 | stt |  | next_due |
| h17 | stt |  | services |
| h19 | stt |  | visit_type |

Raw per-note predictions vs gold: `results.json`.
