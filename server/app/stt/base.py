"""Speech-to-text provider interface (T-023). The server holds all keys; the phone never
calls a vendor. Providers are swapped by config (STT_PROVIDER) and compared in the eval."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from typing import Protocol


class SttError(RuntimeError):
    pass


class NotConfigured(SttError):
    """Provider needs a key/model that is not present."""


@dataclass(frozen=True)
class Transcript:
    text: str
    provider: str
    confidence: float | None = None  # mean word confidence where the provider gives one
    duration_s: float | None = None


class SttProvider(Protocol):
    name: str

    def transcribe(self, wav_bytes: bytes, language: str = "hi") -> Transcript: ...


def wav_info(wav_bytes: bytes) -> tuple[int, int, int, float]:
    """(sample_rate, channels, sample_width_bytes, duration_s). Raises SttError if not WAV."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            rate, ch, width, frames = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    except (wave.Error, EOFError) as exc:
        raise SttError(f"not a PCM WAV file: {exc}") from exc
    return rate, ch, width, frames / float(rate or 1)


def to_mono16k(wav_bytes: bytes) -> bytes:
    """Return 16 kHz mono 16-bit PCM frames (raw, no header). Simple linear resampling,
    enough for speech; recorder sample rates vary by phone (R-15)."""
    import array

    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise SttError(f"need 16-bit PCM, got {8 * width}-bit")
    samples = array.array("h", raw)
    if ch > 1:
        samples = array.array("h", (int(sum(samples[i:i + ch]) / ch) for i in range(0, len(samples), ch)))
    if rate == 16000:
        return samples.tobytes()
    n_out = int(len(samples) * 16000 / rate)
    step = rate / 16000
    out = array.array("h", [0] * n_out)
    last = len(samples) - 1
    for i in range(n_out):
        pos = i * step
        j = int(pos)
        frac = pos - j
        a = samples[min(j, last)]
        b = samples[min(j + 1, last)]
        out[i] = int(a + (b - a) * frac)
    return out.tobytes()
