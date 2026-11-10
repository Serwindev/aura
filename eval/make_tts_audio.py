"""Make AI-voice test audio for the eval notes with Sarvam text-to-speech (bulbul:v3).

AI voices are clean and well paced: this measures the audio path end to end, NOT field accuracy
(real ASHA speech is noisier, dialectal and code-mixed). Audio is synthetic and stays out of git
(`eval/data/audio/` is ignored). Needs SARVAM_API_KEY in server/.env.

Usage:  uv run --project server python eval/make_tts_audio.py --notes eval/data/notes_holdout.yaml
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.core.config import load_yaml  # noqa: E402
from app.core.settings import load_dotenv  # noqa: E402

TTS_URL = "https://api.sarvam.ai/text-to-speech"


def has_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default=str(ROOT / "eval" / "data" / "notes_holdout.yaml"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "data" / "audio"))
    args = ap.parse_args()
    load_dotenv()
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        sys.exit("SARVAM_API_KEY not set (server/.env)")
    out = Path(args.out) / Path(args.notes).stem
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=90) as client:
        for n in load_yaml(Path(args.notes))["notes"]:
            path = out / f"{n['id']}.wav"
            if path.exists():
                continue
            lang = "hi-IN" if has_devanagari(n["transcript"]) else "en-IN"
            r = client.post(TTS_URL, headers={"api-subscription-key": key},
                            json={"text": n["transcript"], "target_language_code": lang,
                                  "model": "bulbul:v3", "speech_sample_rate": 16000})
            if r.status_code != 200:
                print(f"{n['id']}: TTS failed {r.status_code} {r.text[:200]}")
                continue
            path.write_bytes(b"".join(base64.b64decode(a) for a in r.json()["audios"]))
            print(f"{n['id']}: {lang} -> {path.name}")


if __name__ == "__main__":
    main()
