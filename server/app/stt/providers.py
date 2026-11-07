"""STT providers: mock (tests/demo without audio), Vosk (offline Hindi), Sarvam (needs key)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .base import NotConfigured, SttError, Transcript, to_mono16k, wav_info

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
VOSK_HI_MODEL = MODELS_DIR / "vosk-model-small-hi-0.22"


class MockStt:
    """Returns a fixed transcript. Labelled SIMULATED wherever it is shown."""

    name = "mock"

    def __init__(self, text: str = "") -> None:
        self.text = text

    def transcribe(self, wav_bytes: bytes, language: str = "hi") -> Transcript:
        return Transcript(self.text, "mock (SIMULATED)", None, None)


class VoskStt:
    """Offline Hindi ASR (Apache-2.0 model, ~42 MB, CPU). Audio never leaves the machine."""

    name = "vosk"
    _lock = threading.Lock()
    _model = None

    def __init__(self, model_dir: Path = VOSK_HI_MODEL) -> None:
        if not model_dir.is_dir():
            raise NotConfigured(f"Vosk model not found at {model_dir} (see docs/providers.md)")
        self.model_dir = model_dir

    def _load(self):
        with VoskStt._lock:
            if VoskStt._model is None:
                import vosk

                vosk.SetLogLevel(-1)
                VoskStt._model = vosk.Model(str(self.model_dir))
        return VoskStt._model

    def transcribe(self, wav_bytes: bytes, language: str = "hi") -> Transcript:
        if language != "hi":
            raise SttError("Vosk model loaded here is Hindi only")
        import vosk

        _, _, _, duration = wav_info(wav_bytes)
        pcm = to_mono16k(wav_bytes)
        rec = vosk.KaldiRecognizer(self._load(), 16000)
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
        return Transcript(text, "vosk-small-hi-0.22", conf, duration)


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
