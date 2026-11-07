import pytest
from pydantic import ValidationError

from app.core.schema import VisitRecord


def test_empty_record_is_valid_and_all_null():
    r = VisitRecord()
    assert r.schema_version == "0.1"
    assert r.visit_type is None and r.vitals.weight_kg is None
    assert r.danger_signs == [] and r.evidence == {}


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        VisitRecord.model_validate({"visit_type": "HBNC", "diagnosis": "x"})


def test_unknown_visit_type_rejected():
    with pytest.raises(ValidationError):
        VisitRecord.model_validate({"visit_type": "SURGERY"})


def test_roundtrip_json():
    r = VisitRecord.model_validate({"visit_type": "HBYC", "visit_index": {"hbyc_month": 6},
                                    "evidence": {"visit_type": {"quote": "HBYC"}}})
    assert VisitRecord.model_validate_json(r.model_dump_json()) == r
