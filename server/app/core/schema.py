"""Extraction schema v0.1 (plan.md §5.2). Draft — ANM/clinician review pending.

The same model holds the LLM's proposal (after validation) and the ASHA-confirmed record.
`visit_type` is nullable here on purpose: if the LLM's choice has no evidence, code clears it
and the ASHA must pick one on the review screen.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1"

VisitType = Literal[
    "ANC", "PNC", "HBNC", "HBYC", "IMMUNIZATION", "FAMILY_PLANNING",
    "TB_FOLLOWUP", "NCD_FOLLOWUP", "OTHER",
]
ServiceType = Literal["IFA", "CALCIUM", "VACCINE", "ORS", "ZINC", "COUNSELLING", "OTHER"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Beneficiary(_Strict):
    mention: str | None = None
    matched_id: str | None = None  # set by code (name resolution), never by the LLM
    match_confidence: float | None = Field(default=None, ge=0, le=1)


class VisitIndex(_Strict):
    anc_number: int | None = Field(default=None, ge=1, le=12)
    hbnc_day: int | None = Field(default=None, ge=1, le=60)
    hbyc_month: int | None = Field(default=None, ge=1, le=24)


class Vitals(_Strict):
    weight_kg: float | None = None
    temp_c: float | None = None
    bp_sys: int | None = None
    bp_dia: int | None = None
    hb_g_dl: float | None = None
    pulse: int | None = None
    resp_rate: int | None = None


class DangerSign(_Strict):
    code: str
    present: bool | None = None


class Service(_Strict):
    type: ServiceType
    detail: str | None = None


class Referral(_Strict):
    needed: bool | None = None
    facility: str | None = None
    reason: str | None = None


class NextDue(_Strict):
    what: str
    date: Date | None = None


class Evidence(_Strict):
    quote: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class VisitRecord(_Strict):
    schema_version: Literal["0.1"] = SCHEMA_VERSION
    visit_type: VisitType | None = None
    visit_date: Date | None = None
    beneficiary: Beneficiary = Field(default_factory=Beneficiary)
    visit_index: VisitIndex = Field(default_factory=VisitIndex)
    vitals: Vitals = Field(default_factory=Vitals)
    danger_signs: list[DangerSign] = Field(default_factory=list)
    services_given: list[Service] = Field(default_factory=list)
    referral: Referral = Field(default_factory=Referral)
    next_due: list[NextDue] = Field(default_factory=list)
    note: str | None = None
    evidence: dict[str, Evidence] = Field(default_factory=dict)
