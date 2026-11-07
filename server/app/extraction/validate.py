"""Deterministic validation of an LLM-proposed visit record (plan.md §5.2 hard rules).

The LLM proposes; this module decides what survives. Every rule here has a test.

1. Not said → null. Every non-null field needs an evidence quote found in the transcript;
   otherwise the field is cleared and flagged (the proposed value is kept in the flag so the
   review screen can show "heard X? please check").
2. Numbers are re-derived from the quote by the normaliser; mismatch → cleared + flagged.
3. Ranges from rules/validation.yaml; out of range → cleared + flagged.
4. Dates are resolved in code against the recording date.
5. Danger-sign codes must be in the fixed list.
6. Schema errors never crash the pipeline: offending fields are cleared and flagged.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import ValidationError

from ..core.config import ValidationConfig, validation_config
from ..core.schema import VisitRecord
from .dates_hi import resolve_date
from .normalize import (
    contains_quote,
    find_bp,
    numbers_in,
    temperature_c_candidates,
    weight_kg_candidates,
)

Severity = Literal["error", "warning", "info"]

# flag codes
SCHEMA_INVALID = "SCHEMA_INVALID"
MISSING_EVIDENCE = "MISSING_EVIDENCE"
QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
VALUE_MISMATCH = "VALUE_MISMATCH"
OUT_OF_RANGE = "OUT_OF_RANGE"
UNKNOWN_CODE = "UNKNOWN_DANGER_SIGN"
DATE_RESOLVED = "DATE_RESOLVED"
DATE_UNVERIFIED = "DATE_UNVERIFIED"
DATE_IN_FUTURE = "DATE_IN_FUTURE"
DEFAULTED = "DEFAULTED"
UNIT_CONVERTED = "UNIT_CONVERTED"
CROSS_FIELD = "CROSS_FIELD"
OFF_SCHEDULE = "OFF_SCHEDULE"
NEEDS_CHOICE = "NEEDS_CHOICE"


@dataclass
class Flag:
    path: str
    code: str
    severity: Severity
    message: str
    proposed: Any = None
    quote: str | None = None


@dataclass
class ValidationResult:
    record: VisitRecord
    flags: list[Flag] = field(default_factory=list)

    @property
    def needs_review(self) -> list[Flag]:
        order = {"error": 0, "warning": 1, "info": 2}
        return sorted(self.flags, key=lambda f: order[f.severity])

    def flags_for(self, path: str) -> list[Flag]:
        return [f for f in self.flags if f.path == path]


_SCALAR_PATHS = [
    "visit_type", "visit_date", "note", "beneficiary.mention",
    "visit_index.anc_number", "visit_index.hbnc_day", "visit_index.hbyc_month",
    "vitals.weight_kg", "vitals.temp_c", "vitals.bp_sys", "vitals.bp_dia",
    "vitals.hb_g_dl", "vitals.pulse", "vitals.resp_rate",
    "referral.needed", "referral.facility", "referral.reason",
]
_LIST_PATHS = ["danger_signs", "services_given", "next_due"]
_INT_FIELDS = {"bp_sys", "bp_dia", "pulse", "resp_rate"}


def _get(data: dict, path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


_CONTAINERS = {"beneficiary", "visit_index", "vitals", "referral", "evidence",
               "danger_signs", "services_given", "next_due", "schema_version"}


def _schema_pass(raw: dict, flags: list[Flag]) -> dict:
    """Validate against the schema; clear offending fields instead of failing."""
    data = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    for _ in range(100):
        try:
            return VisitRecord.model_validate(data).model_dump()
        except ValidationError as exc:
            for err in exc.errors():
                loc = list(err["loc"])
                flags.append(Flag(_loc_str(loc), SCHEMA_INVALID, "error",
                                  f"Invalid value: {err['msg']}", proposed=err.get("input")))
                _drop(data, loc, err["type"] == "extra_forbidden")
    raise RuntimeError("schema repair did not converge")  # pragma: no cover


def _loc_str(loc: list) -> str:
    out = ""
    for p in loc:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out


def _drop(data: dict, loc: list, extra: bool) -> None:
    """Repair the thing at loc: list items and evidence entries are removed whole;
    containers and unknown keys are removed (defaults restore them); scalars become None."""
    if len(loc) >= 2 and loc[0] == "evidence":
        (data.get("evidence") or {}).pop(loc[1], None)
        return
    cur: Any = data
    for i, p in enumerate(loc):
        if isinstance(cur, list):
            if isinstance(p, int) and p < len(cur):
                cur.pop(p)
            return
        if not isinstance(cur, dict) or p not in cur:
            return
        if i == len(loc) - 1:
            if extra or (i == 0 and p in _CONTAINERS):
                cur.pop(p)
            else:
                cur[p] = None
            return
        cur = cur[p]


def validate_extraction(
    raw: dict,
    transcript: str,
    recorded_on: date,
    config: ValidationConfig | None = None,
) -> ValidationResult:
    cfg = config or validation_config()
    flags: list[Flag] = []
    data = _schema_pass(raw, flags)
    evidence: dict[str, dict] = data.get("evidence") or {}
    # code-owned fields: the LLM may not set these
    data["beneficiary"]["matched_id"] = None
    data["beneficiary"]["match_confidence"] = None

    def quote_ok(path: str, value: Any) -> str | None:
        ev = evidence.get(path)
        if not ev or not ev.get("quote"):
            flags.append(Flag(path, MISSING_EVIDENCE, "error",
                              "No supporting words found — please check", proposed=value))
            return None
        if not contains_quote(transcript, ev["quote"]):
            flags.append(Flag(path, QUOTE_NOT_FOUND, "error",
                              "Quoted words are not in the recording — please check",
                              proposed=value, quote=ev["quote"]))
            return None
        return ev["quote"]

    # 1. evidence for scalar fields
    quotes: dict[str, str] = {}
    for path in _SCALAR_PATHS:
        value = _get(data, path)
        if value is None:
            continue
        q = quote_ok(path, value)
        if q is None:
            _set(data, path, None)
        else:
            quotes[path] = q

    # a date the schema rejected (e.g. "kal") can still be resolved from its quote
    ev_vd = evidence.get("visit_date")
    if ("visit_date" not in quotes and ev_vd and contains_quote(transcript, ev_vd["quote"])
            and resolve_date(ev_vd["quote"], recorded_on, "past") is not None):
        quotes["visit_date"] = ev_vd["quote"]
        flags[:] = [f for f in flags if not (f.path == "visit_date" and f.code == SCHEMA_INVALID)]

    # 1b. evidence for list items (whole item kept or dropped; evidence re-keyed)
    list_evidence: dict[str, dict] = {}
    for lp in _LIST_PATHS:
        kept = []
        for idx, item in enumerate(data[lp]):
            path = f"{lp}[{idx}]"
            q = quote_ok(path, item)
            if q is None:
                continue
            if lp == "danger_signs" and item["code"] not in cfg.danger_codes:
                flags.append(Flag(path, UNKNOWN_CODE, "error",
                                  f"Unknown danger sign '{item['code']}'", proposed=item, quote=q))
                continue
            if lp == "next_due":
                item = _resolve_due(item, q, recorded_on, path, flags)
            list_evidence[f"{lp}[{len(kept)}]"] = evidence[path]
            kept.append(item)
        data[lp] = kept

    vt = data.get("visit_type")

    # 2. numbers re-derived from quotes
    _check_vitals(data, quotes, flags)
    _check_index(data, quotes, flags, cfg)

    # 3. ranges
    for fld, value in list(data["vitals"].items()):
        if value is None:
            continue
        rng = cfg.range_for(vt, fld)
        if rng and not (rng[0] <= value <= rng[1]):
            path = f"vitals.{fld}"
            flags.append(Flag(path, OUT_OF_RANGE, "error",
                              f"{value} is outside the expected range {rng[0]}–{rng[1]}",
                              proposed=value, quote=quotes.get(path)))
            data["vitals"][fld] = None

    # cross-field: BP
    v = data["vitals"]
    if v["bp_sys"] is not None and v["bp_dia"] is not None and v["bp_sys"] <= v["bp_dia"]:
        for f in ("bp_sys", "bp_dia"):
            flags.append(Flag(f"vitals.{f}", CROSS_FIELD, "error",
                              "Systolic must be higher than diastolic", proposed=v[f]))
            v[f] = None

    # 4. visit date
    _resolve_visit_date(data, quotes, recorded_on, flags)

    if data.get("visit_type") is None:
        flags.append(Flag("visit_type", NEEDS_CHOICE, "error", "Please choose the visit type"))

    # keep only evidence for fields that survived
    scalar_ev = {k: evidence[k] for k in quotes if k in evidence and _get(data, k) is not None}
    data["evidence"] = {**scalar_ev, **list_evidence}
    return ValidationResult(VisitRecord.model_validate(data), flags)


def _close(a: float, b: float, tol: float = 0.011) -> bool:
    return abs(a - b) <= tol


def _check_vitals(data: dict, quotes: dict[str, str], flags: list[Flag]) -> None:
    v = data["vitals"]

    def mismatch(fld: str, cands: list) -> None:
        path = f"vitals.{fld}"
        flags.append(Flag(path, VALUE_MISMATCH, "error",
                          f"Value does not match the spoken words (heard: {cands or 'no number'})",
                          proposed=v[fld], quote=quotes[path]))
        v[fld] = None

    for fld in ("bp_sys", "bp_dia"):
        path = f"vitals.{fld}"
        if v[fld] is None:
            continue
        bps = find_bp(quotes[path])
        cands = [b.systolic if fld == "bp_sys" else b.diastolic for b in bps] or numbers_in(quotes[path])
        if not any(_close(v[fld], c) for c in cands):
            mismatch(fld, cands)

    if v["weight_kg"] is not None:
        cands = weight_kg_candidates(quotes["vitals.weight_kg"])
        if not any(_close(v["weight_kg"], c) for c in cands):
            mismatch("weight_kg", cands)

    if v["temp_c"] is not None:
        path = "vitals.temp_c"
        cands = temperature_c_candidates(quotes[path])
        match = next((c for c in cands if _close(v["temp_c"], c[0], 0.11)), None)
        if match is None:
            # LLM may have copied °F into temp_c: accept if the raw number matches, convert in code
            raw_f = [q for q in numbers_in(quotes[path]) if 90 <= q <= 110]
            if any(_close(v["temp_c"], f) for f in raw_f):
                conv = round((v["temp_c"] - 32) * 5 / 9, 1)
                flags.append(Flag(path, UNIT_CONVERTED, "info",
                                  f"Converted {v['temp_c']} °F to {conv} °C",
                                  proposed=v["temp_c"], quote=quotes[path]))
                v["temp_c"] = conv
            else:
                mismatch("temp_c", [c[0] for c in cands])
        elif match[1]:
            flags.append(Flag(path, UNIT_CONVERTED, "info",
                              f"Spoken in °F; stored as {match[0]} °C", quote=quotes[path]))
            v["temp_c"] = match[0]

    for fld in ("hb_g_dl", "pulse", "resp_rate"):
        if v[fld] is None:
            continue
        cands = numbers_in(quotes[f"vitals.{fld}"])
        if not any(_close(v[fld], c) for c in cands):
            mismatch(fld, cands)
        elif fld in _INT_FIELDS:
            v[fld] = int(round(v[fld]))


def _check_index(data: dict, quotes: dict[str, str], flags: list[Flag], cfg: ValidationConfig) -> None:
    vi = data["visit_index"]
    for fld in ("anc_number", "hbnc_day", "hbyc_month"):
        if vi[fld] is None:
            continue
        path = f"visit_index.{fld}"
        cands = numbers_in(quotes[path])
        if not any(_close(vi[fld], c) for c in cands):
            flags.append(Flag(path, VALUE_MISMATCH, "error",
                              f"Value does not match the spoken words (heard: {cands or 'no number'})",
                              proposed=vi[fld], quote=quotes[path]))
            vi[fld] = None
    if vi["hbnc_day"] is not None and cfg.hbnc_days and vi["hbnc_day"] not in cfg.hbnc_days:
        flags.append(Flag("visit_index.hbnc_day", OFF_SCHEDULE, "warning",
                          f"Day {vi['hbnc_day']} is not a scheduled HBNC day "
                          f"{sorted(cfg.hbnc_days)}"))
    if vi["hbyc_month"] is not None and cfg.hbyc_months and vi["hbyc_month"] not in cfg.hbyc_months:
        flags.append(Flag("visit_index.hbyc_month", OFF_SCHEDULE, "warning",
                          f"Month {vi['hbyc_month']} is not a scheduled HBYC month "
                          f"{sorted(cfg.hbyc_months)}"))


def _resolve_visit_date(data: dict, quotes: dict[str, str], recorded_on: date, flags: list[Flag]) -> None:
    path = "visit_date"
    proposed = data.get("visit_date")
    if path in quotes:
        resolved = resolve_date(quotes[path], recorded_on, "past")
        if resolved is not None:
            if resolved != proposed:
                flags.append(Flag(path, DATE_RESOLVED, "info",
                                  f"Date worked out from the words: {resolved.isoformat()}",
                                  proposed=proposed, quote=quotes[path]))
            data[path] = resolved
        else:
            flags.append(Flag(path, DATE_UNVERIFIED, "warning",
                              "Could not confirm the date from the words — please check",
                              proposed=proposed, quote=quotes[path]))
    if data.get(path) is None:
        data[path] = recorded_on
        flags.append(Flag(path, DEFAULTED, "info", "Visit date not spoken; using recording date"))
    elif data[path] > recorded_on:
        flags.append(Flag(path, DATE_IN_FUTURE, "error", "Visit date is after the recording date",
                          proposed=data[path]))
        data[path] = recorded_on


def _resolve_due(item: dict, quote: str, recorded_on: date, path: str, flags: list[Flag]) -> dict:
    item = dict(item)
    resolved = resolve_date(quote, recorded_on, "future")
    if resolved is not None:
        if resolved != item.get("date"):
            flags.append(Flag(path, DATE_RESOLVED, "info",
                              f"Due date worked out from the words: {resolved.isoformat()}",
                              proposed=item.get("date"), quote=quote))
        item["date"] = resolved
    elif item.get("date") is not None:
        flags.append(Flag(path, DATE_UNVERIFIED, "warning",
                          "Could not confirm the due date from the words — please check",
                          proposed=item["date"], quote=quote))
    return item
