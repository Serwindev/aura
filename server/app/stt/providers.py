"""STT providers: Sarvam Saaras v4 (cloud; default when a key exists), Vosk (offline; fallback),
mock (tests; SIMULATED)."""

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

    def transcribe(self, wav_bytes: bytes, language: str = "hi", hints: list[str] | None = None) -> Transcript:
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

    def transcribe(self, wav_bytes: bytes, language: str = "hi", hints: list[str] | None = None) -> Transcript:
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


SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_MODEL = "saaras:v4"
SARVAM_LANG = {"hi": "hi-IN", "en": "en-IN"}
CHUNK_MAX_S = 28.0  # REST accepts < 30 s; longer notes are split at the quietest point
CHUNK_MIN_S = 18.0
# Domain words the model should prefer (Sarvam "keyterms", v4 only, max 50 terms x 64 chars).
DOMAIN_TERMS = ("ASHA", "ANM", "HBNC", "HBYC", "BCG", "OPV", "Pentavalent", "Rotavirus", "IPV",
                "PCV", "MR", "Vitamin A", "DPT", "Hepatitis B", "ORS", "IFA", "PHC", "CHC")


def split_pcm(pcm: bytes, rate: int = 16000) -> list[bytes]:
    """Split 16-bit mono PCM into chunks under CHUNK_MAX_S, cutting at the quietest 50 ms frame
    between CHUNK_MIN_S and CHUNK_MAX_S so words are not cut in half."""
    import array

    samples = array.array("h", pcm)
    frame = rate // 20
    lo, hi = int(CHUNK_MIN_S * rate), int(CHUNK_MAX_S * rate)
    chunks: list[bytes] = []
    start = 0
    while len(samples) - start > hi:
        best, best_energy = start + hi, None
        for at in range(start + lo, start + hi - frame, frame):
            energy = sum(abs(x) for x in samples[at:at + frame:4])
            if best_energy is None or energy <= best_energy:  # latest quiet point: fewer chunks
                best, best_energy = at + frame // 2, energy
        chunks.append(samples[start:best].tobytes())
        start = best
    chunks.append(samples[start:].tobytes())
    return [c for c in chunks if len(c) >= rate // 5]  # drop slivers under 0.1 s


def pcm_to_wav(pcm: bytes, rate: int = 16000) -> bytes:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def keyterms(hints: list[str] | None) -> list[str]:
    seen: list[str] = []
    for term in (*(hints or ()), *DOMAIN_TERMS):
        term = term.strip()[:64]
        if term and term not in seen:
            seen.append(term)
    return seen[:50]


class SarvamHttpError(SttError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class SarvamStt:
    """Sarvam Saaras v4 (cloud, REST). The server sends audio to Sarvam (India); the phone never
    calls a vendor. Notes over 28 s are split and transcribed in parts. If Sarvam cannot be
    reached, the offline fallback (Vosk) is used and the provider label says so."""

    name = "sarvam"

    def __init__(self, api_key: str | None = None, fallback=None, client=None, timeout: float = 40.0) -> None:
        self.api_key = (api_key or os.environ.get("SARVAM_API_KEY", "")).strip()
        if not self.api_key:
            raise NotConfigured("SARVAM_API_KEY not set (put it in server/.env)")
        self.fallback = fallback
        self.timeout = timeout
        self._client = client

    def languages(self) -> list[str]:
        return list(SARVAM_LANG)

    def _post(self, wav: bytes, language: str, terms: list[str]) -> dict:
        import httpx

        data = {"model": SARVAM_MODEL, "language_code": SARVAM_LANG.get(language, "unknown"),
                "mode": "transcribe"}
        if terms:
            data["keyterms"] = json.dumps(terms, ensure_ascii=False)
        client = self._client or httpx.Client(timeout=self.timeout)
        try:
            r = client.post(SARVAM_URL, headers={"api-subscription-key": self.api_key}, data=data,
                            files={"file": ("note.wav", wav, "audio/wav")})
        finally:
            if self._client is None:
                client.close()
        if r.status_code != 200:
            try:
                err = r.json().get("error", {})
                msg = f"{err.get('code', '')}: {err.get('message', '')}"
            except ValueError:
                msg = r.text[:200]
            raise SarvamHttpError(r.status_code, f"Sarvam {r.status_code} {msg}")
        return r.json()

    def transcribe(self, wav_bytes: bytes, language: str = "hi", hints: list[str] | None = None) -> Transcript:
        import httpx

        _, _, _, duration = wav_info(wav_bytes)
        terms = keyterms(hints)
        try:
            parts = [self._post(pcm_to_wav(c), language, terms) for c in split_pcm(to_mono16k(wav_bytes))]
        except (httpx.TransportError, SarvamHttpError) as exc:
            retryable = isinstance(exc, httpx.TransportError) or exc.status in (429, 500, 502, 503, 504)
            if self.fallback is None or not retryable:
                raise SttError(f"speech service failed: {exc}") from exc
            tr = self.fallback.transcribe(wav_bytes, language)
            return Transcript(tr.text, f"{tr.provider} (offline fallback: Sarvam unreachable)",
                              tr.confidence, tr.duration_s)
        text = " ".join(p.get("transcript", "").strip() for p in parts).strip()
        return Transcript(text, "sarvam-" + SARVAM_MODEL.replace(":", "-"), None, duration)


def _vosk_or_none():
    try:
        return VoskStt()
    except NotConfigured:
        return None


def get_stt(name: str | None = None):
    name = (name or os.environ.get("STT_PROVIDER") or "auto").lower()
    if name == "auto":
        name = "sarvam" if os.environ.get("SARVAM_API_KEY", "").strip() else "vosk"
    if name == "mock":
        return MockStt()
    if name == "vosk":
        return VoskStt()
    if name == "sarvam":
        return SarvamStt(fallback=_vosk_or_none())
    raise NotConfigured(f"unknown STT provider {name!r}")
