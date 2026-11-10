# Eval results — 2026-11-10 (Sarvam speech-to-text)

All notes are synthetic and written by the same developer (Claude) who wrote the extractor.
Audio is **AI voice** (Sarvam `bulbul:v3` text-to-speech, made by `eval/make_tts_audio.py`), not
real ASHA speech. AI voices are clean, and Sarvam TTS → Sarvam STT is a same-vendor pairing, so
these figures are optimistic. They show the audio path works end to end; they are **not field
accuracy**. Attach this caveat to any number used on a slide.

| Folder | What | Tuned on it? |
|---|---|---|
| `holdout-audio-sarvam/` | 20 held-out notes, audio → Sarvam `saaras:v4` → extractor. **First run, before any fix.** | No — the honest figure |
| `holdout-audio-vosk/` | Same audio → offline Vosk small models (the old default) | No |
| `holdout-audio-sarvam-after-fixes/` | Same as the first row after two extractor fixes found by looking at held-out audio output ("102 डिग्री" with no temperature word; "दूध भी नहीं पी") | **Yes — optimistic** |
| `holdout/`, `dev/` | Text-only regression runs after the fixes | holdout: partly (see above); dev: yes |

Headline (first run, untuned):

| | Sarvam saaras:v4 | Vosk small (old) |
|---|---|---|
| Notes with every critical field right | 17/20 (0.85) | 6/20 (0.30) |
| Field F1 | 0.93 | 0.70 |
| Raw word error rate (no number/spelling normalisation) | 0.125 | 0.344 |
| STT time per note, median | 0.65 s (cloud) | 1.7 s (this laptop) |
| Unsupported values | 0.000 | 0.000 |

Reproduce: `uv run --project server python eval/make_tts_audio.py --notes eval/data/notes_holdout.yaml`
then `uv run --project server python eval/harness.py --notes eval/data/notes_holdout.yaml --audio-dir eval/data/audio/notes_holdout --stt sarvam --out <dir>`.
Audio files are git-ignored (`eval/data/audio/`).
