"""Voice/text note → validated record (plan §5.1 stages 2–6).

audio ─STT─▶ transcript ─extract─▶ raw (LLM-shaped) ─validate─▶ record + flags ─names─▶ matched id
Never auto-submits: the result is a DRAFT for the review screen.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .core.config import REPO_ROOT, ValidationConfig, load_yaml
from .core.schema import Evidence
from .extraction import rule_based
from .extraction.details import extract_details
from .extraction.llm import LlmExtractor, LlmUnavailable
from .extraction.llm import from_env as llm_from_env
from .extraction.names import NameMatch, Person, resolve_beneficiary
from .extraction.validate import ValidationResult, validate_extraction
from .stt.base import Transcript

REGISTRY_PATH = REPO_ROOT / "eval" / "data" / "registry.yaml"
log = logging.getLogger(__name__)


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


_UNSET = object()


def process_transcript(transcript: Transcript, recorded_on: date, people: list[Person],
                       llm: LlmExtractor | None | object = _UNSET,
                       config: ValidationConfig | None = None) -> PipelineResult:
    """llm: an LlmExtractor, None for rule-based, or unset = from the environment (LLM_PROVIDER).
    If the LLM cannot give a proposal, the rule-based extractor is used and the note is never lost."""
    if llm is _UNSET:
        llm = llm_from_env()
    t0 = time.perf_counter()
    name = "rule-based-v0"
    raw = None
    if llm is not None:
        try:
            raw = llm.extract(transcript.text, recorded_on)
            name = llm.name
        except LlmUnavailable as exc:
            log.warning("LLM extractor unavailable (%s); using rule-based", exc)  # no transcript in logs
            name = "rule-based-v0 (LLM fallback)"
    if raw is None:
        raw = rule_based.extract(transcript.text, recorded_on, people)
    t1 = time.perf_counter()
    result = validate_extraction(raw, transcript.text, recorded_on, config)
    for d in extract_details(transcript.text):  # extra form details (D-39); visit scope only
        result.record.extras[d.id] = d.value
        result.record.evidence[f"extras.{d.id}"] = Evidence(quote=d.quote)
        # "mother temperature 99" is the mother's, not the baby's: the baby's temperature yields
        baby_t = result.record.evidence.get("vitals.temp_c")
        if d.id == "mother_temp_f" and baby_t and (baby_t.quote in d.quote or d.quote in baby_t.quote):
            result.record.vitals.temp_c = None
            del result.record.evidence["vitals.temp_c"]
    t2 = time.perf_counter()
    match = resolve_beneficiary(transcript.text, people, result.record.visit_type)
    if match and match.matched_id:
        result.record.beneficiary.matched_id = match.matched_id
        result.record.beneficiary.match_confidence = min(1.0, match.confidence)
    t3 = time.perf_counter()
    return PipelineResult(transcript, name, raw, result, match, {
        "extract": (t1 - t0) * 1000, "validate": (t2 - t1) * 1000, "names": (t3 - t2) * 1000})


def process_text(text: str, recorded_on: date, people: list[Person],
                 llm: LlmExtractor | None | object = _UNSET, config: ValidationConfig | None = None) -> PipelineResult:
    return process_transcript(Transcript(text, "typed"), recorded_on, people, llm, config)


def process_audio(wav_bytes: bytes, recorded_on: date, people: list[Person], stt,
                  language: str = "hi", llm: LlmExtractor | None | object = _UNSET,
                  config: ValidationConfig | None = None) -> PipelineResult:
    t0 = time.perf_counter()
    # names in the register help the speech model spell them (Latin for English, Devanagari for Hindi)
    hints = sorted({n for p in people for n in p.names if n.isascii() == (language == "en")})
    tr = stt.transcribe(wav_bytes, language, hints=hints)
    stt_ms = (time.perf_counter() - t0) * 1000
    res = process_transcript(tr, recorded_on, people, llm, config)
    res.timings_ms["stt"] = stt_ms
    return res
