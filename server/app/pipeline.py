"""Voice/text note → validated record (plan §5.1 stages 2–6).

audio ─STT─▶ transcript ─extract─▶ raw (LLM-shaped) ─validate─▶ record + flags ─names─▶ matched id
Never auto-submits: the result is a DRAFT for the review screen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .core.config import REPO_ROOT, load_yaml
from .extraction import rule_based
from .extraction.names import NameMatch, Person, resolve_beneficiary
from .extraction.validate import ValidationResult, validate_extraction
from .stt.base import Transcript

REGISTRY_PATH = REPO_ROOT / "eval" / "data" / "registry.yaml"


def load_people(path: Path = REGISTRY_PATH) -> list[Person]:
    out = []
    for p in load_yaml(path)["people"]:
        out.append(Person(id=p["id"], names=tuple(p.get("names") or ()), category=p["category"],
                          mother_id=p.get("mother_id"), dob=p.get("dob"),
                          delivery_place=p.get("delivery_place"),
                          label_hi=p.get("label_hi"), label_en=p.get("label_en")))
    return out


@dataclass
class PipelineResult:
    transcript: Transcript
    extractor: str
    raw: dict
    validation: ValidationResult
    match: NameMatch | None
    timings_ms: dict[str, float] = field(default_factory=dict)


def process_transcript(transcript: Transcript, recorded_on: date, people: list[Person],
                       extractor: str = "rule") -> PipelineResult:
    if extractor != "rule":
        raise ValueError(f"extractor {extractor!r} not available (no LLM key configured)")
    t0 = time.perf_counter()
    raw = rule_based.extract(transcript.text, recorded_on, people)
    t1 = time.perf_counter()
    result = validate_extraction(raw, transcript.text, recorded_on)
    t2 = time.perf_counter()
    match = resolve_beneficiary(transcript.text, people, result.record.visit_type)
    if match and match.matched_id:
        result.record.beneficiary.matched_id = match.matched_id
        result.record.beneficiary.match_confidence = min(1.0, match.confidence)
    t3 = time.perf_counter()
    return PipelineResult(transcript, "rule-based-v0", raw, result, match, {
        "extract": (t1 - t0) * 1000, "validate": (t2 - t1) * 1000, "names": (t3 - t2) * 1000})


def process_text(text: str, recorded_on: date, people: list[Person]) -> PipelineResult:
    return process_transcript(Transcript(text, "typed"), recorded_on, people)


def process_audio(wav_bytes: bytes, recorded_on: date, people: list[Person], stt,
                  language: str = "hi") -> PipelineResult:
    t0 = time.perf_counter()
    tr = stt.transcribe(wav_bytes, language)
    stt_ms = (time.perf_counter() - t0) * 1000
    res = process_transcript(tr, recorded_on, people)
    res.timings_ms["stt"] = stt_ms
    return res
