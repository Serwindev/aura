"""T-020/T-024 hard rules (plan §5.2): each rule has at least one test here.
All names and values are synthetic."""

import copy
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.config import validation_config
from app.core.schema import VisitRecord
from app.extraction import validate as V
from app.extraction.validate import validate_extraction

REC = date(2026, 11, 10)
T1 = ("आज सुनीता के बच्चे का तीसरे दिन का HBNC विज़िट किया। बच्चे का वजन दो किलो आठ सौ ग्राम है। "
      "तापमान सौ डिग्री है। दूध ठीक से पी रहा है। BP 120 by 80. अगली विज़िट सातवें दिन, चार दिन बाद।")


def ev(quote):
    return {"quote": quote, "confidence": 0.9}


def good_raw():
    return {
        "schema_version": "0.1",
        "visit_type": "HBNC",
        "visit_date": "2026-11-10",
        "beneficiary": {"mention": "सुनीता के बच्चे"},
        "visit_index": {"hbnc_day": 3},
        "vitals": {"weight_kg": 2.8, "temp_c": 37.8},
        "next_due": [{"what": "HBNC day 7", "date": "2026-11-14"}],
        "evidence": {
            "visit_type": ev("HBNC विज़िट"),
            "visit_date": ev("आज"),
            "beneficiary.mention": ev("सुनीता के बच्चे"),
            "visit_index.hbnc_day": ev("तीसरे दिन"),
            "vitals.weight_kg": ev("वजन दो किलो आठ सौ ग्राम"),
            "vitals.temp_c": ev("तापमान सौ डिग्री"),
            "next_due[0]": ev("चार दिन बाद"),
        },
    }


def errors(res):
    return [f for f in res.flags if f.severity == "error"]


def codes(res, path):
    return {f.code for f in res.flags_for(path)}


def test_happy_path():
    res = validate_extraction(good_raw(), T1, REC)
    assert errors(res) == []
    r = res.record
    assert r.visit_type == "HBNC"
    assert r.visit_date == REC
    assert r.visit_index.hbnc_day == 3
    assert r.vitals.weight_kg == 2.8
    assert r.vitals.temp_c == 37.8
    assert r.next_due[0].date == date(2026, 11, 14)
    assert "vitals.weight_kg" in r.evidence and "next_due[0]" in r.evidence
    assert V.UNIT_CONVERTED in codes(res, "vitals.temp_c")


def test_input_not_mutated():
    raw = good_raw()
    before = copy.deepcopy(raw)
    validate_extraction(raw, T1, REC)
    assert raw == before


def test_missing_evidence_clears_field():
    raw = good_raw()
    raw["vitals"]["pulse"] = 120
    res = validate_extraction(raw, T1, REC)
    assert res.record.vitals.pulse is None
    (flag,) = [f for f in res.flags if f.path == "vitals.pulse"]
    assert flag.code == V.MISSING_EVIDENCE and flag.proposed == 120


def test_hallucinated_quote_clears_field():
    raw = good_raw()
    raw["vitals"]["hb_g_dl"] = 9.5
    raw["evidence"]["vitals.hb_g_dl"] = ev("Hb 9.5")  # never said
    res = validate_extraction(raw, T1, REC)
    assert res.record.vitals.hb_g_dl is None
    assert codes(res, "vitals.hb_g_dl") == {V.QUOTE_NOT_FOUND}


def test_number_not_matching_quote_is_flagged():
    raw = good_raw()
    raw["vitals"]["weight_kg"] = 3.2
    res = validate_extraction(raw, T1, REC)
    assert res.record.vitals.weight_kg is None
    (flag,) = res.flags_for("vitals.weight_kg")
    assert flag.code == V.VALUE_MISMATCH and flag.proposed == 3.2


def test_out_of_range_for_visit_type():
    t = "HBNC विज़िट। वजन अट्ठाईस किलो।"
    raw = {"visit_type": "HBNC", "vitals": {"weight_kg": 28},
           "evidence": {"visit_type": ev("HBNC विज़िट"), "vitals.weight_kg": ev("वजन अट्ठाईस किलो")}}
    res = validate_extraction(raw, t, REC)
    assert res.record.vitals.weight_kg is None
    assert V.OUT_OF_RANGE in codes(res, "vitals.weight_kg")
    # the same weight is plausible for another visit type (default range)
    raw2 = copy.deepcopy(raw)
    raw2["visit_type"] = "OTHER"
    raw2["evidence"]["visit_type"] = ev("विज़िट")
    assert validate_extraction(raw2, t, REC).record.vitals.weight_kg == 28


def test_fahrenheit_copied_into_temp_c_is_converted():
    raw = good_raw()
    raw["vitals"]["temp_c"] = 100
    res = validate_extraction(raw, T1, REC)
    assert res.record.vitals.temp_c == 37.8
    assert V.UNIT_CONVERTED in codes(res, "vitals.temp_c")


def test_bp_ok_and_bp_swapped():
    raw = good_raw()
    raw["vitals"].update(bp_sys=120, bp_dia=80)
    raw["evidence"].update({"vitals.bp_sys": ev("BP 120 by 80"), "vitals.bp_dia": ev("BP 120 by 80")})
    res = validate_extraction(raw, T1, REC)
    assert (res.record.vitals.bp_sys, res.record.vitals.bp_dia) == (120, 80)

    raw["vitals"].update(bp_sys=80, bp_dia=120)
    res = validate_extraction(raw, T1, REC)
    assert res.record.vitals.bp_sys is None and res.record.vitals.bp_dia is None


def test_bp_cross_field():
    t = "BP 80 by 120"
    raw = {"visit_type": "ANC", "vitals": {"bp_sys": 80, "bp_dia": 120},
           "evidence": {"visit_type": ev("BP"), "vitals.bp_sys": ev(t), "vitals.bp_dia": ev(t)}}
    res = validate_extraction(raw, t, REC)
    assert res.record.vitals.bp_sys is None
    assert V.CROSS_FIELD in codes(res, "vitals.bp_dia")


def test_unknown_danger_sign_dropped_and_evidence_rekeyed():
    t = "बच्चे को बुखार है। बच्चा उदास है।"
    raw = {"visit_type": "OTHER",
           "danger_signs": [{"code": "SAD", "present": True}, {"code": "NB_FEVER", "present": True}],
           "evidence": {"visit_type": ev("बच्चे"), "danger_signs[0]": ev("बच्चा उदास है"),
                        "danger_signs[1]": ev("बच्चे को बुखार है")}}
    res = validate_extraction(raw, t, REC)
    assert [d.code for d in res.record.danger_signs] == ["NB_FEVER"]
    assert res.record.evidence["danger_signs[0]"].quote == "बच्चे को बुखार है"
    assert V.UNKNOWN_CODE in codes(res, "danger_signs[0]")


def test_list_item_without_evidence_dropped():
    raw = good_raw()
    raw["services_given"] = [{"type": "IFA", "detail": None}]
    res = validate_extraction(raw, T1, REC)
    assert res.record.services_given == []
    assert V.MISSING_EVIDENCE in codes(res, "services_given[0]")


def test_garbage_does_not_crash():
    raw = {"visit_type": "XYZ", "vitals": {"weight_kg": "abc", "foo": 1}, "bar": 2,
           "danger_signs": "fever", "next_due": [{"date": "kal"}],
           "evidence": {"x": {"confidence": 5}}}
    res = validate_extraction(raw, T1, REC)
    assert isinstance(res.record, VisitRecord)
    assert res.record.visit_type is None
    assert V.NEEDS_CHOICE in codes(res, "visit_type")
    assert any(f.code == V.SCHEMA_INVALID for f in res.flags)


@pytest.mark.parametrize("raw", [None, [], "text", 42])
def test_non_dict_input(raw):
    res = validate_extraction(raw, T1, REC)
    assert res.record.visit_type is None


def test_relative_visit_date_string_resolved_from_quote():
    t = "कल HBNC विज़िट किया"
    raw = {"visit_type": "HBNC", "visit_date": "kal",
           "evidence": {"visit_type": ev("HBNC विज़िट"), "visit_date": ev("कल")}}
    res = validate_extraction(raw, t, REC)
    assert res.record.visit_date == date(2026, 11, 9)
    assert V.SCHEMA_INVALID not in codes(res, "visit_date")


def test_wrong_llm_date_corrected_by_code():
    raw = good_raw()
    raw["visit_date"] = "2026-11-01"  # LLM got "आज" wrong
    res = validate_extraction(raw, T1, REC)
    assert res.record.visit_date == REC
    assert V.DATE_RESOLVED in codes(res, "visit_date")


def test_visit_date_defaults_to_recording_date():
    raw = good_raw()
    del raw["visit_date"]
    del raw["evidence"]["visit_date"]
    res = validate_extraction(raw, T1, REC)
    assert res.record.visit_date == REC
    assert codes(res, "visit_date") == {V.DEFAULTED}


def test_future_visit_date_rejected():
    raw = good_raw()
    raw["visit_date"] = "2026-11-20"
    raw["evidence"]["visit_date"] = ev("HBNC विज़िट")  # quote has no date in it
    res = validate_extraction(raw, T1, REC)
    assert res.record.visit_date == REC
    assert {V.DATE_UNVERIFIED, V.DATE_IN_FUTURE} <= codes(res, "visit_date")


def test_llm_cannot_set_matched_id():
    raw = good_raw()
    raw["beneficiary"]["matched_id"] = "6f1c1d1e-0000-4000-8000-000000000001"
    raw["beneficiary"]["match_confidence"] = 0.99
    res = validate_extraction(raw, T1, REC)
    assert res.record.beneficiary.matched_id is None
    assert res.record.beneficiary.match_confidence is None


def test_off_schedule_hbnc_day_warns_but_keeps():
    t = "पांचवें दिन HBNC विज़िट"
    raw = {"visit_type": "HBNC", "visit_index": {"hbnc_day": 5},
           "evidence": {"visit_type": ev("HBNC विज़िट"), "visit_index.hbnc_day": ev("पांचवें दिन")}}
    res = validate_extraction(raw, t, REC)
    assert res.record.visit_index.hbnc_day == 5
    assert codes(res, "visit_index.hbnc_day") == {V.OFF_SCHEDULE}


def test_needs_review_orders_errors_first():
    raw = good_raw()
    raw["vitals"]["pulse"] = 120
    res = validate_extraction(raw, T1, REC)
    sev = [f.severity for f in res.needs_review]
    assert sev == sorted(sev, key={"error": 0, "warning": 1, "info": 2}.get)


def test_config_schedules_come_from_rules_yaml():
    cfg = validation_config()
    assert cfg.hbnc_days == {1, 3, 7, 14, 21, 28, 42}
    assert cfg.hbyc_months == {3, 6, 9, 12, 15}
    assert "NB_FEVER" in cfg.danger_codes
    assert cfg.status == "draft"


# property: a value whose quote is not in the transcript never survives
@settings(max_examples=200)
@given(
    weight=st.floats(min_value=0.5, max_value=6, allow_nan=False),
    hb=st.floats(min_value=3, max_value=20, allow_nan=False),
    pulse=st.integers(min_value=40, max_value=220),
    quote=st.text(alphabet="xyzXYZ0123456789 .", max_size=20),
)
def test_no_evidence_no_value(weight, hb, pulse, quote):
    raw = {"visit_type": "HBNC", "vitals": {"weight_kg": weight, "hb_g_dl": hb, "pulse": pulse},
           "evidence": {"vitals.weight_kg": ev(quote), "vitals.hb_g_dl": ev(quote),
                        "vitals.pulse": ev(quote)}}
    res = validate_extraction(raw, "कुछ नहीं बोला गया", REC)
    v = res.record.vitals
    assert v.weight_kg is None and v.hb_g_dl is None and v.pulse is None
