"""LLM extractor (T-024) with a fake client: no network, no API credit. Synthetic data only.
The point: whatever the model proposes, the validator and the fallback keep the record safe."""

from __future__ import annotations

from datetime import date

import pytest

from app.extraction import llm as L
from app.extraction.validate import MISSING_EVIDENCE, QUOTE_NOT_FOUND, UNKNOWN_CODE, VALUE_MISMATCH
from app.pipeline import load_people, process_text

DAY = date(2026, 11, 9)
NOTE = "Visited Sunita Devi baby today, newborn visit day 7. Weight is 2.8 kg, no fever. BCG given."
PEOPLE = load_people()


class FakeResp:
    def __init__(self, status, payload):
        self.status_code, self.payload = status, payload

    def json(self):
        return self.payload


class FakeHttp:
    """Stands in for httpx.Client: returns an OpenAI-compatible chat completion."""
    def __init__(self, result=None, exc=None, status=200, finish="stop", content=None, refusal=None):
        self.result, self.exc, self.status, self.finish = result, exc, status, finish
        self.content, self.refusal, self.calls = content, refusal, []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.exc:
            raise self.exc
        content = self.content if self.content is not None else (
            self.result.model_dump_json(exclude_none=True) if self.result is not None else "not json")
        msg = {"role": "assistant", "content": content, "refusal": self.refusal}
        return FakeResp(self.status, {"choices": [{"message": msg, "finish_reason": self.finish}],
                                      "usage": {"prompt_tokens": 100, "completion_tokens": 50}})


def fake(result=None, **kw) -> L.LlmExtractor:
    return L.LlmExtractor(provider="ollama", model="qwen2.5:3b", base_url="http://localhost:11434/v1",
                          client=FakeHttp(result, **kw))


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
    assert res.extractor == "llm:ollama/qwen2.5:3b (llm-v2)"
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
    ex.api_key = "test-key"
    ex.extract(NOTE, DAY)
    call = ex.client.calls[0]
    assert call["url"] == "http://localhost:11434/v1/chat/completions"
    assert call["headers"] == {"Authorization": "Bearer test-key"}
    body = call["json"]
    assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
    assert "Recorded on: 2026-11-09" in body["messages"][1]["content"] and NOTE in body["messages"][1]["content"]
    sys_text = body["messages"][0]["content"]
    assert NOTE not in sys_text and "NB_FEVER" in sys_text and "Penta-2" in sys_text  # stable prompt
    assert '"beneficiary_mention"' in sys_text  # the JSON schema travels in the prompt


def test_fenced_json_is_accepted():
    ex = fake(content="```json\n" + good().model_dump_json(exclude_none=True) + "\n```")
    assert ex.extract(NOTE, DAY)["vitals"]["weight_kg"] == 2.8


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


@pytest.mark.parametrize("kw", [{"exc": ConnectionError("down")}, {"status": 429}, {"status": 500},
                                {"refusal": "no"}, {"finish": "length"}, {"content": "not json"},
                                {"content": '{"visit_type": {"value": "WRONG", "quote": "x"}}'}])
def test_llm_failure_falls_back_to_rule_based(kw):
    ex = fake(**({"result": good()} | kw))
    res = process_text(NOTE, DAY, PEOPLE, llm=ex)
    assert res.extractor == "rule-based-v0 (LLM fallback)"
    assert res.validation.record.vitals.weight_kg == 2.8  # rule-based still did the job


def test_env_switch(monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert L.from_env() is None
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    assert L.from_env() is None
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")  # removed: Claude is no longer an option
    assert L.from_env() is None
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    ex = L.from_env()
    assert (ex.model, ex.cloud) == ("qwen2.5:3b", False)
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    assert L.from_env() is None  # no model set for a cloud preset -> rule-based
    monkeypatch.setenv("LLM_MODEL", "some-free-model")
    monkeypatch.setenv("LLM_API_KEY", "k")
    ex = L.from_env()
    assert ex.cloud and ex.base_url.startswith("https://api.groq.com") and ex.api_key == "k"
    monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
    assert L.from_env() is None  # needs LLM_BASE_URL
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
    assert L.from_env().cloud is False


def test_default_pipeline_stays_rule_based(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert process_text(NOTE, DAY, PEOPLE).extractor == "rule-based-v0"


def test_usage_is_reported():
    ex = fake(good())
    ex.extract(NOTE, DAY)
    assert (ex.usage[0]["input"], ex.usage[0]["output"]) == (100, 50)
