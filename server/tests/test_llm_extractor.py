"""LLM extractor (T-024) with a fake client: no network, no API credit. Synthetic data only.
The point: whatever the model proposes, the validator and the fallback keep the record safe."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.extraction import llm as L
from app.extraction.validate import MISSING_EVIDENCE, QUOTE_NOT_FOUND, UNKNOWN_CODE, VALUE_MISMATCH
from app.pipeline import load_people, process_text

DAY = date(2026, 11, 9)
NOTE = "Visited Sunita Devi baby today, newborn visit day 7. Weight is 2.8 kg, no fever. BCG given."
PEOPLE = load_people()


class FakeMessages:
    def __init__(self, result=None, exc=None, stop="end_turn"):
        self.result, self.exc, self.stop, self.calls = result, exc, stop, []

    def parse(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc
        usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=1000,
                                cache_creation_input_tokens=0)
        return SimpleNamespace(parsed_output=self.result, stop_reason=self.stop, usage=usage)


def fake(result=None, **kw) -> L.LlmExtractor:
    return L.LlmExtractor(model="claude-haiku-5-5", client=SimpleNamespace(messages=FakeMessages(result, **kw)))


def good() -> L.Proposal:
    return L.Proposal(
        visit_type=L.VisitTypeV(value="HBNC", quote="newborn visit"),
        visit_date=L.TextV(value="2026-11-09", quote="today"),
        beneficiary_mention=L.TextV(value="Sunita Devi baby", quote="Sunita Devi baby"),
        hbnc_day=L.IntV(value=7, quote="day 7"),
        weight_kg=L.NumV(value=2.8, quote="Weight is 2.8 kg"),
        danger_signs=[L.DangerV(code="NB_FEVER", present=False, quote="no fever")],
        services_given=[L.ServiceV(type="VACCINE", detail="BCG", quote="BCG given")],
    )


def test_good_proposal_becomes_validated_record():
    ex = fake(good())
    res = process_text(NOTE, DAY, PEOPLE, llm=ex)
    r = res.validation.record
    assert res.extractor == "llm:claude-haiku-5-5:llm-v1"
    assert (r.visit_type, r.visit_index.hbnc_day, r.vitals.weight_kg) == ("HBNC", 7, 2.8)
    assert r.visit_date == DAY
    assert r.beneficiary.matched_id == "c01"  # set by code, never by the model
    assert [(d.code, d.present) for d in r.danger_signs] == [("NB_FEVER", False)]
    assert r.services_given[0].detail == "BCG"
    assert r.evidence["vitals.weight_kg"].quote == "Weight is 2.8 kg"
    assert r.evidence["vitals.weight_kg"].confidence is None  # no invented confidence
    assert not [f for f in res.validation.flags if f.severity == "error"]


def test_request_shape():
    ex = fake(good())
    ex.extract(NOTE, DAY)
    kw = ex.client.messages.calls[0]
    assert kw["output_format"] is L.Proposal
    assert kw["output_config"] == {"effort": "low"}
    assert "Recorded on: 2026-11-09" in kw["messages"][0]["content"]
    assert NOTE in kw["messages"][0]["content"]
    sys_text = kw["system"][0]["text"]
    assert NOTE not in sys_text and "NB_FEVER" in sys_text and "Penta-2" in sys_text  # stable, cacheable
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_invented_quote_is_cleared_and_flagged():
    p = good()
    p.temp = L.NumV(value=38.5, quote="temperature 38.5")  # not in the note: a hallucination
    res = process_text(NOTE, DAY, PEOPLE, llm=fake(p))
    assert res.validation.record.vitals.temp_c is None
    assert any(f.path == "vitals.temp_c" and f.code == QUOTE_NOT_FOUND for f in res.validation.flags)


def test_number_not_matching_its_quote_is_cleared():
    p = good()
    p.weight_kg = L.NumV(value=3.8, quote="Weight is 2.8 kg")
    res = process_text(NOTE, DAY, PEOPLE, llm=fake(p))
    assert res.validation.record.vitals.weight_kg is None
    assert any(f.path == "vitals.weight_kg" and f.code == VALUE_MISMATCH for f in res.validation.flags)


def test_empty_quote_is_missing_evidence():
    p = good()
    p.hbnc_day = L.IntV(value=7, quote="")
    res = process_text(NOTE, DAY, PEOPLE, llm=fake(p))
    assert res.validation.record.visit_index.hbnc_day is None
    assert any(f.code == MISSING_EVIDENCE for f in res.validation.flags)


def test_unknown_danger_code_is_dropped():
    p = good()
    p.danger_signs.append(L.DangerV(code="NB_MADE_UP", present=True, quote="no fever"))
    res = process_text(NOTE, DAY, PEOPLE, llm=fake(p))
    assert [d.code for d in res.validation.record.danger_signs] == ["NB_FEVER"]
    assert any(f.code == UNKNOWN_CODE for f in res.validation.flags)


def test_future_visit_date_is_not_kept():
    p = good()
    p.visit_date = L.TextV(value="2026-11-20", quote="today")
    res = process_text(NOTE, DAY, PEOPLE, llm=fake(p))
    assert res.validation.record.visit_date == DAY  # re-resolved from the quote in code


def test_nothing_said_stays_null():
    res = process_text("Visited Sunita Devi baby.", DAY, PEOPLE, llm=fake(L.Proposal()))
    v = res.validation.record.vitals
    assert all(getattr(v, f) is None for f in ("weight_kg", "temp_c", "bp_sys", "hb_g_dl"))


@pytest.mark.parametrize("kw", [{"exc": ConnectionError("down")}, {"stop": "refusal"}, {"stop": "max_tokens"},
                                {"result": None}])
def test_llm_failure_falls_back_to_rule_based(kw):
    ex = fake(**({"result": good()} | kw))
    res = process_text(NOTE, DAY, PEOPLE, llm=ex)
    assert res.extractor == "rule-based-v0 (LLM fallback)"
    assert res.validation.record.vitals.weight_kg == 2.8  # rule-based still did the job


def test_env_switch(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert L.from_env() is None
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert L.from_env() is None
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5-5")
    ex = L.from_env()
    assert ex.model == "claude-sonnet-5-5" and ex.effort == "low"


def test_default_pipeline_stays_rule_based(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert process_text(NOTE, DAY, PEOPLE).extractor == "rule-based-v0"


def test_cost_is_reported():
    ex = fake(good())
    ex.extract(NOTE, DAY)
    # 100 in * 0.10 + 50 out * 0.50 + 1000 cache-read * 0.01 per million
    assert ex.cost_usd() == pytest.approx((100 * 0.10 + 50 * 0.50 + 1000 * 0.01) / 1e6)
    assert ex.usage[0]["output"] == 50
