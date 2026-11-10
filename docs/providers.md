# Providers (T-023 / T-006)

Status as of 2026-11-07. "Vendor claim" = not measured by us.

## Speech-to-text

| Provider | Status | Licence / terms | Notes |
|---|---|---|---|
| **Vosk `vosk-model-small-en-in-0.4`** | Offline Indian English for English-language notes (D-20). End-to-end path verified with Windows TTS; accuracy **not measured**, and names were misheard in that test. | Apache-2.0 (Vosk models page) | About 55 MB on disk. Install: `.\make.ps1 models`. |
| **Vosk `vosk-model-small-hi-0.22`** | **Default for v1.** Offline, CPU, no key. Plumbing verified (load, 22→16 kHz resample, transcribe); Hindi accuracy **not measured by us** (no recordings yet). | Apache-2.0 (Vosk models page) | ~42 MB. Vendor-reported WER (model README): 20.9% (IITM test), 24.7% (MUCS), 39.1% (gram), 15.0% (TTS set) — vendor claim. Outputs Devanagari words, no punctuation, numbers as words → our normaliser handles this. Install: `.\make.ps1 models`. |
| Sarvam Saaras v4 | **Default** since 2026-11-10 (`saaras:v4`; chunks < 30 s; register names as key terms; Vosk fallback). Eval: `eval/results/2026-11-10/` | Commercial; ₹30/h, ₹1,000 signup credit [S5][S29] | REST < 30 s. Zero-retention default is a vendor claim. |
| Bhashini / Dhruva | Not started — needs ULCA userID + key | Gov platform; ToS [U9] | Two-step pipeline config → inference. |
| IndicConformer-600M | **Dropped on this machine** (D-14: no CUDA, 7 GB RAM) | MIT, gated HF | Revisit with a GPU machine. |

## Extraction

| Extractor | Status | Notes |
|---|---|---|
| **Rule-based v0** (`server/app/extraction/rule_based.py`) | **Default for v1.** Offline, deterministic, no key. | Eval 2026-11-07: dev set (40, tuned on) F1 0.99; **held-out (20, scored once) P 0.99 / R 0.87 / F1 0.93, critical 16/20** — synthetic, same author; see `eval/results/2026-11-07/`. Misses rather than invents. |
| Claude (`claude-haiku-5-5` / `sonnet-5-5`) structured output | Not built — needs an Anthropic key | Same raw shape → same validator; bake-off vs rule-based when available (T-026). |
