"""Phase 2: STT plumbing, name resolution, rule-based extractor, pipeline. Synthetic data only."""

import io
import math
import struct
import wave
from datetime import date
from pathlib import Path

import pytest

from app.core.config import REPO_ROOT, load_yaml
from app.extraction import rule_based
from app.extraction.names import Person, resolve_beneficiary
from app.extraction.validate import QUOTE_NOT_FOUND, validate_extraction
from app.pipeline import load_people, process_audio, process_text
from app.stt.base import SttError, wav_info
from app.stt.base import to_mono16k as resample
from app.stt.providers import VOSK_HI_MODEL, MockStt, NotConfigured, VoskStt

REC = date(2026, 11, 10)
PEOPLE = load_people()


def make_wav(rate=22050, seconds=0.5, channels=1, freq=440.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / rate))) * channels
            for i in range(int(rate * seconds)))
        w.writeframes(frames)
    return buf.getvalue()


# ---- STT plumbing ----------------------------------------------------------

def test_wav_info_and_resample():
    wav = make_wav(rate=22050, seconds=1.0, channels=2)
    rate, ch, width, dur = wav_info(wav)
    assert (rate, ch, width) == (22050, 2, 2) and dur == pytest.approx(1.0)
    pcm = resample(wav)
    assert len(pcm) // 2 == pytest.approx(16000, abs=2)


def test_not_a_wav_is_rejected():
    with pytest.raises(SttError):
        wav_info(b"not audio at all")


def test_mock_is_labelled_simulated():
    assert "SIMULATED" in MockStt("x").transcribe(make_wav()).provider


def test_vosk_missing_model_is_not_configured(tmp_path):
    with pytest.raises(NotConfigured):
        VoskStt(tmp_path / "nope")


@pytest.mark.skipif(not VOSK_HI_MODEL.is_dir(), reason="Vosk Hindi model not downloaded")
def test_vosk_runs_on_tone():
    tr = VoskStt().transcribe(make_wav(seconds=1.0))
    assert isinstance(tr.text, str) and tr.provider.startswith("vosk")


def test_audio_pipeline_with_mock_stt():
    stt = MockStt("आज सुनीता की बच्ची का HBNC विज़िट किया। वज़न 2.8 किलो।")
    res = process_audio(make_wav(), REC, PEOPLE, stt)
    assert res.validation.record.vitals.weight_kg == 2.8
    assert "stt" in res.timings_ms


# ---- names ----------------------------------------------------------------

@pytest.mark.parametrize(("text", "vt", "expected"), [
    ("सुनीता की बच्ची का विजिट", "HBNC", "c01"),
    ("कविता के बेटे आरव का HBYC", "HBYC", "c04"),
    ("आरव का टीका", "IMMUNIZATION", "c04"),
    ("Meena ki beti Ananya", "IMMUNIZATION", "c05"),
    ("रेखा के घर नवजात विजिट", "HBNC", "c02"),     # mother's name only, one newborn
    ("सुनीता देवी का PNC", "PNC", "w01"),           # mother-focused visit → the mother
    ("पूजा यादव का ANC", "ANC", "w03"),
    ("Sunitha ki beti", "HBNC", "c01"),              # fuzzy Latin spelling
])
def test_resolve(text, vt, expected):
    m = resolve_beneficiary(text, PEOPLE, vt)
    assert m is not None and m.matched_id == expected


def test_unknown_person_returns_none():
    assert resolve_beneficiary("रमेश जी के घर", PEOPLE, "TB_FOLLOWUP") is None


def test_two_people_first_wins_with_lower_confidence():
    m = resolve_beneficiary("रेखा के बच्चे का विजिट, फिर गीता से मिली", PEOPLE, "HBNC")
    assert m.matched_id == "c02" and m.confidence < 1 and set(m.candidates) == {"c02", "w06"}


def test_mother_with_several_children_needs_child_name():
    people = [Person("m", ("सीमा",), "other"),
              Person("k1", ("राजू",), "child", mother_id="m"), Person("k2", ("सोनू",), "child", mother_id="m")]
    assert resolve_beneficiary("सीमा के बच्चे का टीका", people, "IMMUNIZATION") is None
    assert resolve_beneficiary("सीमा के बेटे सोनू का टीका", people, "IMMUNIZATION").matched_id == "k2"


# ---- rule-based extractor -------------------------------------------------

def all_notes():
    for name in ("notes.yaml", "notes_holdout.yaml"):
        yield from load_yaml(REPO_ROOT / "eval" / "data" / name)["notes"]


@pytest.mark.parametrize("note", list(all_notes()), ids=lambda n: n["id"])
def test_extractor_quotes_are_always_real(note):
    """Invariant: the rule-based extractor only ever quotes text that is really there."""
    raw = rule_based.extract(note["transcript"], note["recorded_on"], PEOPLE)
    res = validate_extraction(raw, note["transcript"], note["recorded_on"])
    assert not [f for f in res.flags if f.code == QUOTE_NOT_FOUND]


def test_age_is_not_a_date():
    raw = rule_based.extract("3 दिन का बच्चा है, HBNC विज़िट", REC, PEOPLE)
    assert "visit_date" not in raw


def test_negated_vaccine_not_recorded():
    raw = rule_based.extract("आज ईशान को एमआर का टीका नहीं लगा", REC, PEOPLE)
    assert not raw.get("services_given")


def test_visit_word_daura_is_not_convulsions():
    raw = rule_based.extract("आज रेखा के बच्चे का नवजात दौरा किया", REC, PEOPLE)
    assert not raw.get("danger_signs")


def test_pipeline_sets_matched_id_and_never_invents_one():
    r = process_text("आज सुनीता की बच्ची का HBNC विज़िट", REC, PEOPLE)
    assert r.validation.record.beneficiary.matched_id == "c01"
    r = process_text("हाँ जी ठीक है बाद में बात करते हैं", REC, PEOPLE)
    assert r.validation.record.beneficiary.matched_id is None
    assert r.validation.record.visit_type is None


def test_dev_set_regression_guard():
    """Guards against regressions on the (overfit) dev set; NOT an accuracy claim."""
    import subprocess
    import sys

    out = Path(REPO_ROOT / "eval" / "harness.py")
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(out), "--out", str(Path(__file__).parent / ".eval_tmp")],
                          capture_output=True, text=True, encoding="utf-8", env=env)
    assert proc.returncode == 0, proc.stderr
    f1 = float(proc.stdout.split("F1=")[1].split()[0])
    assert f1 >= 0.95, proc.stdout
