"""STT providers: mock (tests/demo without audio), Vosk (offline Hindi), Sarvam (needs key)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .base import NotConfigured, SttError, Transcript, to_mono16k, wav_info

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
VOSK_HI_MODEL = MODELS_DIR / "vosk-model-small-hi-0.22"
VOSK_EN_MODEL = MODELS_DIR / "vosk-model-small-en-in-0.4"
VOSK_MODELS = {"hi": VOSK_HI_MODEL, "en": VOSK_EN_MODEL}


class MockStt:
    """Returns a fixed transcript. Labelled SIMULATED wherever it is shown."""

    name = "mock"

    def __init__(self, text: str = "") -> None:
        self.text = text

    def transcribe(self, wav_bytes: bytes, language: str = "hi") -> Transcript:
        return Transcript(self.text, "mock (SIMULATED)", None, None)


class VoskStt:
    """Offline ASR, Hindi and Indian English (Apache-2.0 models, CPU). Audio never leaves the
    machine."""

    name = "vosk"
    _lock = threading.Lock()
    _models: dict[Path, object] = {}

    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dirs = {"hi": model_dir} if model_dir else VOSK_MODELS
        first = model_dir or VOSK_HI_MODEL
        if not first.is_dir():
            raise NotConfigured(f"Vosk model not found at {first} (see docs/providers.md)")

    def _load(self, model_dir: Path):
        with VoskStt._lock:
            if model_dir not in VoskStt._models:
                import vosk

                vosk.SetLogLevel(-1)
                VoskStt._models[model_dir] = vosk.Model(str(model_dir))
        return VoskStt._models[model_dir]

    def languages(self) -> list[str]:
        return [lang for lang, path in self.model_dirs.items() if path.is_dir()]

    def transcribe(self, wav_bytes: bytes, language: str = "hi") -> Transcript:
        model_dir = self.model_dirs.get(language)
        if model_dir is None or not model_dir.is_dir():
            raise SttError(f"no speech model installed for language {language!r}")
        import vosk

        _, _, _, duration = wav_info(wav_bytes)
        pcm = to_mono16k(wav_bytes)
        rec = vosk.KaldiRecognizer(self._load(model_dir), 16000)
        rec.SetWords(True)
        words: list[dict] = []
        texts: list[str] = []
        chunk = 8000
        for i in range(0, len(pcm), chunk):
            if rec.AcceptWaveform(pcm[i:i + chunk]):
                r = json.loads(rec.Result())
                texts.append(r.get("text", ""))
                words += r.get("result", [])
        r = json.loads(rec.FinalResult())
        texts.append(r.get("text", ""))
        words += r.get("result", [])
        text = " ".join(t for t in texts if t).strip()
        conf = sum(w.get("conf", 0) for w in words) / len(words) if words else None
        return Transcript(text, model_dir.name.replace("vosk-model-", "vosk-"), conf, duration)


class SarvamStt:
    """Sarvam Saaras (REST, < 30 s audio). Not implemented until a key exists to test it."""

    name = "sarvam"

    def __init__(self) -> None:
        if not os.environ.get("SARVAM_API_KEY"):
            raise NotConfigured("SARVAM_API_KEY not set")
        raise NotConfigured("Sarvam adapter not built yet: needs a key to test against (T-023)")

    def transcribe(self, wav_bytes: bytes, language: str = "hi") -> Transcript:  # pragma: no cover
        raise NotImplementedError


def get_stt(name: str | None = None):
    name = (name or os.environ.get("STT_PROVIDER") or "vosk").lower()
    if name == "mock":
        return MockStt()
    if name == "vosk":
        return VoskStt()
    if name == "sarvam":
        return SarvamStt()
    raise NotConfigured(f"unknown STT provider {name!r}")
