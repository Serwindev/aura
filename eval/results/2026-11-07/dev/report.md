# Eval report — notes — 2026-11-07

> **Read this first.** 40 *synthetic, text-only* notes written by the same developer (Claude) who
> wrote the rule-based extractor. This is a **smoke test of the pipeline**, not evidence of
> real-world accuracy. No audio was recorded, so speech-to-text error (WER/CER) is **not measured**.
> Do not put these numbers on a slide without this caveat.

- Extractor: `rule-based-v0` (deterministic, offline) · STT: none (text transcripts)
- Machine: Windows 11, Python 3.12.10

## Headline

| Metric | Value |
|---|---|
| Field precision / recall / F1 (micro, 254 TP · 2 FP · 1 FN) | 0.99 / 1.00 / 0.99 |
| Notes with every critical field right | 0.97 (39/40) |
| Unsupported values (filled where gold says nothing was said) | 0.000 |
| Text pipeline latency p50 / p95 (extract + validate + names) | 13.1 / 22.5 ms |
| Mean error flags per note (shown to the ASHA for review) | 0.03 |
| STT WER / CER | **not measured** (no recordings) |
| LLM extractor | **not measured** (no API key) |

## By transcript style

| Style | P | R | F1 |
|---|---|---|---|
| clean | 0.98 | 0.99 | 0.99 |
| stt | 1.00 | 1.00 | 1.00 |

## Per field

| Field | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|
| visit_type | 39 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| visit_date | 40 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| beneficiary_id | 38 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hbnc_day | 10 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hbyc_month | 6 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| anc_number | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| weight_kg | 22 | 1 | 1 | 0.96 | 0.96 | 0.96 |
| temp_c | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_sys | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| bp_dia | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| hb_g_dl | 4 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| referral_needed | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| referral_facility | 8 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| danger_signs | 24 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| services | 32 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| next_due | 9 | 1 | 0 | 0.90 | 1.00 | 0.95 |

## Notes with errors

| Note | Style | Tags | Wrong fields |
|---|---|---|---|
| n05 | clean | hard, self_correction | weight_kg |
| n13 | clean | hard, two_people | next_due |

Raw per-note predictions vs gold: `results.json`.
