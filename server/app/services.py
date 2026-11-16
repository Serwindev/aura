"""Business logic between the API and the pipeline: notes, confirmation, tasks, demo seed.

Trust boundary: the client's confirmed record is re-validated here, and evidence is owned by the
server. A field the ASHA changed loses its quote and is logged as edited (paths only, no values).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .core.config import RULES_DIR, load_yaml, schedule_or_default, validation_config
from .core.schema import VisitRecord
from .core.settings import Settings
from .db.models import AuditEvent, Note, Person, TaskAction, User, new_id, utcnow
from .extraction.dates_hi import add_months
from .extraction.names import Person as NamePerson
from .extraction.names import resolve_beneficiary
from .extraction.validate import Flag
from .pipeline import PipelineResult, load_people, process_audio, process_text
from .rules import engine

NEEDS_CHOICE = "NEEDS_CHOICE"
PROGRAMME_VISIT = {"HBNC": "HBNC", "HBYC": "HBYC", "UIP": "IMMUNIZATION"}
SCALAR_PATHS = (
    "visit_type", "visit_date", "beneficiary.matched_id", "visit_index.anc_number",
    "visit_index.hbnc_day", "visit_index.hbyc_month", "vitals.weight_kg", "vitals.temp_c",
    "vitals.bp_sys", "vitals.bp_dia", "vitals.hb_g_dl", "vitals.pulse", "vitals.resp_rate",
    "referral.needed", "referral.facility", "referral.reason", "note",
)
LIST_PATHS = ("danger_signs", "services_given", "next_due")
SEED_ANCHOR = date(2026, 11, 9)  # the date the synthetic registry's birth dates were written for


class RequestError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


@dataclass(frozen=True)
class TaskHint:
    """The ASHA opened this note from a task: an explicit choice of hers, not a model guess."""

    beneficiary_id: str | None = None
    programme: str | None = None
    rule_id: str | None = None


def people_for(db: Session, owner_id: str) -> list[NamePerson]:
    rows = db.scalars(select(Person).where(Person.owner_id == owner_id)).all()
    return [NamePerson(id=p.id, names=tuple(p.names or ()), category=p.category, mother_id=p.mother_id,
                       dob=p.dob, delivery_place=p.delivery_place, label_hi=p.label_hi,
                       label_en=p.label_en, area=p.area, at_risk=p.at_risk) for p in rows]


# ---- doses ---------------------------------------------------------------------------------

def _key(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def dose_table() -> dict[str, str]:
    table = {_key(d["vaccine"]): d["id"] for d in load_yaml(RULES_DIR / "uip.yaml")["doses"]}
    table.update({"hepb": "hepb0", "dpt": "dpt_b1", "dptbooster": "dpt_b1"})
    return table


def dose_id(detail: str | None, table: dict[str, str]) -> str | None:
    return table.get(_key(detail)) if detail else None


# ---- creating drafts -----------------------------------------------------------------------

def _apply_hint(result: PipelineResult, people: list[NamePerson], hint: TaskHint) -> None:
    v = result.validation
    rec = v.record
    known = {p.id for p in people}
    if hint.beneficiary_id in known:
        if rec.beneficiary.matched_id is None:
            rec.beneficiary.matched_id = hint.beneficiary_id
            v.flags.append(Flag("beneficiary.matched_id", "FROM_TASK", "info", "Person taken from the task you opened"))
        elif rec.beneficiary.matched_id != hint.beneficiary_id:
            v.flags.append(Flag("beneficiary.matched_id", "TASK_MISMATCH", "warning",
                                "The name spoken is different from the task you opened"))
    if rec.visit_type is None and hint.programme in PROGRAMME_VISIT:
        rec.visit_type = PROGRAMME_VISIT[hint.programme]
        v.flags = [f for f in v.flags if not (f.path == "visit_type" and f.code == NEEDS_CHOICE)]
        v.flags.append(Flag("visit_type", "FROM_TASK", "info", "Visit type taken from the task you opened"))
    m = re.fullmatch(r"(hbnc_d|hbyc_m)(\d+)", hint.rule_id or "")
    if m:
        if m[1] == "hbnc_d" and rec.visit_type == "HBNC" and rec.visit_index.hbnc_day is None:
            rec.visit_index.hbnc_day = int(m[2])
        if m[1] == "hbyc_m" and rec.visit_type == "HBYC" and rec.visit_index.hbyc_month is None:
            rec.visit_index.hbyc_month = int(m[2])


def _post_flags(result: PipelineResult) -> None:
    v = result.validation
    if v.record.beneficiary.matched_id is None:
        v.flags.append(Flag("beneficiary.matched_id", NEEDS_CHOICE, "error", "Please choose who this visit was for"))
    elif result.match is not None and len(result.match.candidates) > 1:
        v.flags.append(Flag("beneficiary.matched_id", "AMBIGUOUS_NAME", "warning",
                            "More than one person was named; check this is the right one"))
    rec = v.record
    if rec.visit_type == "HBNC" and rec.visit_index.hbnc_day is None:
        v.flags.append(Flag("visit_index.hbnc_day", "NEEDS_DAY", "warning", "Add the HBNC day so the schedule can be updated"))
    if rec.visit_type == "HBYC" and rec.visit_index.hbyc_month is None:
        v.flags.append(Flag("visit_index.hbyc_month", "NEEDS_DAY", "warning", "Add the HBYC month so the schedule can be updated"))
    table = dose_table()
    for i, s in enumerate(v.record.services_given):
        if s.type == "VACCINE" and dose_id(s.detail, table) is None:
            v.flags.append(Flag(f"services_given[{i}]", "NEEDS_DOSE", "warning",
                                "Add the dose number so the schedule can be updated"))


def create_note(db: Session, cfg: Settings, stt: Any, owner_id: str, *, text: str | None, wav: bytes | None,
                language: str, hint: TaskHint, idempotency_key: str | None, recorded_on: date | None = None) -> Note:
    if idempotency_key:
        found = db.scalar(select(Note).where(Note.owner_id == owner_id, Note.idempotency_key == idempotency_key))
        if found:
            return found
    purge_expired_audio(db, cfg)
    people = people_for(db, owner_id)
    today = recorded_on or cfg.today()
    vcfg = validation_config(schedule=user_schedule(db, owner_id))
    if wav is not None:
        result = process_audio(wav, today, people, stt, language, config=vcfg)
    else:
        result = process_text(text or "", today, people, config=vcfg)
    if not result.transcript.text.strip():
        raise RequestError(422, "EMPTY_TRANSCRIPT", "No speech could be recognised in this audio")
    _apply_hint(result, people, hint)
    _post_flags(result)
    note = Note(owner_id=owner_id, idempotency_key=idempotency_key, source="audio" if wav is not None else "text",
                language=language, recorded_on=today, transcript=result.transcript.text,
                stt_provider=result.transcript.provider if wav is not None else None,
                stt_confidence=result.transcript.confidence,
                draft=result.validation.record.model_dump(mode="json"),
                flags=jsonable_encoder([asdict(f) for f in result.validation.needs_review]),
                candidates=result.match.candidates if result.match else [])
    db.add(note)
    try:
        db.flush()
    except IntegrityError:
        # Same idempotency key sent twice at once (e.g. a page reload while a queued note was sending):
        # the other request won the race, so this one returns its note instead of failing.
        db.rollback()
        found = db.scalar(select(Note).where(Note.owner_id == owner_id, Note.idempotency_key == idempotency_key))
        if found is None:
            raise
        return found
    if wav is not None:
        cfg.audio_dir.mkdir(parents=True, exist_ok=True)
        path = cfg.audio_dir / f"{note.id}.wav"
        path.write_bytes(wav)
        note.audio_path = str(path)
    db.add(AuditEvent(owner_id=owner_id, note_id=note.id, action="draft_created", detail={"source": note.source}))
    db.commit()
    return note


def _set(d: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


def add_to_note(db: Session, cfg: Settings, stt: Any, note: Note, *, text: str | None, wav: bytes | None,
                language: str) -> dict:
    """She speaks (or types) more on the review screen. Only what the new words STATE changes — a field
    changes only if the new clip carries a quote for it — and newer speech wins. The machine draft is
    updated (so these are not counted as her manual corrections) and the clip's text is appended to the
    transcript. The added audio is never stored. Returns the changes so the phone can apply them on top
    of her own typed edits."""
    if note.status != "draft":
        raise RequestError(409, "NOT_A_DRAFT", "This note is already confirmed or discarded")
    people = people_for(db, note.owner_id)
    vcfg = validation_config(schedule=user_schedule(db, note.owner_id))
    if wav is not None:
        result = process_audio(wav, note.recorded_on, people, stt, language, config=vcfg)
    else:
        result = process_text(text or "", note.recorded_on, people, config=vcfg)
    added = result.transcript.text.strip()
    if not added:
        raise RequestError(422, "EMPTY_TRANSCRIPT", "No speech could be recognised in this audio")
    new = result.validation.record.model_dump(mode="json")
    ev_new = new.get("evidence") or {}
    draft = jsonable_encoder(note.draft)
    ev = draft.setdefault("evidence", {})
    scalars: dict[str, Any] = {}
    lists: dict[str, list] = {lp: [] for lp in LIST_PATHS}
    remap: dict[str, str] = {}  # flag/evidence path in the clip → path in the draft
    for p in SCALAR_PATHS:
        if p == "beneficiary.matched_id" or p not in ev_new or _get(new, p) is None:
            continue
        _set(draft, p, _get(new, p))
        ev[p] = ev_new[p]
        scalars[p] = _get(new, p)
        remap[p] = p
    match = result.match
    if new.get("visit_type") is None and draft.get("visit_type"):
        # the clip did not say the visit type: "Sunita baby" on a newborn visit is her newborn, not Sunita
        match = resolve_beneficiary(added, people, draft["visit_type"])
    if match and match.matched_id:
        result.match = match
        _set(draft, "beneficiary.matched_id", result.match.matched_id)
        _set(draft, "beneficiary.match_confidence", min(1.0, result.match.confidence))
        if "beneficiary.mention" in ev_new:
            ev["beneficiary.mention"] = ev_new["beneficiary.mention"]
            _set(draft, "beneficiary.mention", _get(new, "beneficiary.mention"))
        scalars["beneficiary.matched_id"] = result.match.matched_id
        remap["beneficiary.matched_id"] = "beneficiary.matched_id"
        note.candidates = result.match.candidates
    for lp in LIST_PATHS:
        cur = draft.setdefault(lp, [])
        for i, item in enumerate(new.get(lp) or []):
            key = f"{lp}[{i}]"
            if key not in ev_new:
                continue
            if lp == "danger_signs":
                j = next((k for k, x in enumerate(cur) if x.get("code") == item["code"]), None)
            elif lp == "next_due":
                j = next((k for k, x in enumerate(cur) if (x.get("what") or "").strip().lower()
                          == (item.get("what") or "").strip().lower()), None)
            else:  # services: the same service twice is one service
                j = next((k for k, x in enumerate(cur) if x == item), None)
            if j is None:
                cur.append(item)
                j = len(cur) - 1
            else:
                cur[j] = item
            ev[f"{lp}[{j}]"] = ev_new[key]
            remap[key] = f"{lp}[{j}]"
            lists[lp].append(item)
    changed = set(remap.values())
    if not changed:
        raise RequestError(422, "NOTHING_NEW", "Nothing new was heard. Say the field and its value, e.g. 'temperature 37'")
    flags = [f for f in note.flags if f["path"] not in changed and f["path"] not in {p.split("[")[0] for p in changed}]
    if "beneficiary.matched_id" in changed:
        flags = [f for f in flags if f["path"] != "beneficiary.matched_id"]
    for f in jsonable_encoder([asdict(f) for f in result.validation.needs_review]):
        if f["path"] in remap:
            flags.append({**f, "path": remap[f["path"]]})
    for p in sorted(changed):
        flags.append(asdict(Flag(p, "VOICE_ADDED", "info", "Changed by your added recording")))
    if draft.get("visit_type") == "HBNC" and _get(draft, "visit_index.hbnc_day") is None \
            and not any(f["path"] == "visit_index.hbnc_day" for f in flags):
        flags.append(asdict(Flag("visit_index.hbnc_day", "NEEDS_DAY", "warning",
                                 "Add the HBNC day so the schedule can be updated")))
    note.draft = draft
    note.flags = jsonable_encoder(flags)
    note.transcript = f"{note.transcript}\n{added}"
    db.add(AuditEvent(owner_id=note.owner_id, note_id=note.id, action="voice_added",
                      detail={"source": "audio" if wav is not None else "text", "paths": sorted(changed)}))
    db.commit()
    return {"added_text": added, "scalars": scalars, **lists}


def delete_audio(note: Note) -> bool:
    if not note.audio_path:
        return False
    Path(note.audio_path).unlink(missing_ok=True)
    note.audio_path = None
    return True


def purge_expired_audio(db: Session, cfg: Settings) -> int:
    """D-07: delete on confirm, and never keep unconfirmed audio past the retention cap."""
    cutoff = utcnow() - timedelta(hours=cfg.audio_retention_hours)
    stale = db.scalars(select(Note).where(Note.audio_path.is_not(None), Note.created_at < cutoff)).all()
    for n in stale:
        delete_audio(n)
    if stale:
        db.commit()
    return len(stale)


# ---- confirmation --------------------------------------------------------------------------

def _get(d: dict, path: str) -> Any:
    for part in path.split("."):
        d = (d or {}).get(part)
    return d


def user_schedule(db: Session, owner_id: str) -> str:
    """Her chosen visit schedule (D-32); the 2014/2018 guidelines unless she picked SSBSK 2026 in Settings."""
    u = db.get(User, owner_id)
    return schedule_or_default(u.schedule if u else None)


def _check_record(rec: VisitRecord, people: list[NamePerson], today: date, schedule: str | None = None) -> list[dict]:
    cfg = validation_config(schedule=schedule_or_default(schedule))
    errs: list[dict] = []

    def err(path: str, code: str, message: str) -> None:
        errs.append({"path": path, "code": code, "message": message})

    if rec.visit_type is None:
        err("visit_type", NEEDS_CHOICE, "Please choose the visit type")
    if rec.visit_date is None:
        err("visit_date", NEEDS_CHOICE, "Please enter the visit date")
    elif rec.visit_date > today:
        err("visit_date", "DATE_IN_FUTURE", "The visit date cannot be in the future")
    if rec.beneficiary.matched_id not in {p.id for p in people}:
        err("beneficiary.matched_id", NEEDS_CHOICE, "Please choose who this visit was for")
    for fld, value in rec.vitals.model_dump().items():
        rng = cfg.range_for(rec.visit_type, fld)
        if value is not None and rng and not (rng[0] <= value <= rng[1]):
            err(f"vitals.{fld}", "OUT_OF_RANGE", f"{value} is outside the expected range {rng[0]}–{rng[1]}")
    v = rec.vitals
    if v.bp_sys is not None and v.bp_dia is not None and v.bp_sys <= v.bp_dia:
        err("vitals.bp_sys", "CROSS_FIELD", "Systolic must be higher than diastolic")
    if rec.visit_type == "HBNC" and rec.visit_index.hbnc_day not in (None, *cfg.hbnc_days):
        err("visit_index.hbnc_day", "OFF_SCHEDULE", "This is not an HBNC schedule day")
    if rec.visit_type == "HBYC" and rec.visit_index.hbyc_month not in (None, *cfg.hbyc_months):
        err("visit_index.hbyc_month", "OFF_SCHEDULE", "This is not an HBYC schedule month")
    for i, d in enumerate(rec.danger_signs):
        if d.code not in cfg.danger_codes:
            err(f"danger_signs[{i}]", "UNKNOWN_DANGER_SIGN", "Unknown danger sign")
    return errs


def confirm_note(db: Session, cfg: Settings, note: Note, payload: dict) -> tuple[Note, bool]:
    """Human confirmation. Repeating a confirm returns the stored record unchanged."""
    if note.status == "confirmed":
        return note, False
    if note.status != "draft":
        raise RequestError(409, "NOT_A_DRAFT", "This note has been discarded")
    payload = dict(payload)
    payload["evidence"] = {}  # evidence is server-owned; never accepted from the client
    try:
        rec = VisitRecord.model_validate(payload)
    except ValidationError as exc:
        details = [{"path": ".".join(str(p) for p in e["loc"]), "code": "SCHEMA_INVALID", "message": e["msg"]}
                   for e in exc.errors()]
        raise RequestError(422, "INVALID_RECORD", "Some fields are not valid", details) from exc
    errors = _check_record(rec, people_for(db, note.owner_id), cfg.today(), user_schedule(db, note.owner_id))
    if errors:
        raise RequestError(422, "CHECK_FIELDS", "Please check the highlighted fields", errors)

    new = rec.model_dump(mode="json")
    old = note.draft
    edited = [p for p in SCALAR_PATHS if _get(old, p) != _get(new, p)]
    evidence: dict = {}
    for p, ev in (old.get("evidence") or {}).items():
        m = re.fullmatch(r"(\w+)\[(\d+)\]", p)
        if m:
            o, n = old.get(m[1]) or [], new.get(m[1]) or []
            i = int(m[2])
            if i < len(o) and i < len(n) and o[i] == n[i]:
                evidence[p] = ev
        elif p not in edited:
            evidence[p] = ev
    for lp in LIST_PATHS:
        if (old.get(lp) or []) != (new.get(lp) or []):
            edited.append(lp)
    new["evidence"] = evidence
    note.confirmed, note.edited_paths, note.status = new, edited, "confirmed"
    note.confirmed_at = utcnow()
    audio_deleted = delete_audio(note)
    db.add(AuditEvent(owner_id=note.owner_id, note_id=note.id, action="confirmed",
                      detail={"edited": edited, "audio_deleted": audio_deleted}))
    db.commit()
    return note, audio_deleted


# ---- tasks ---------------------------------------------------------------------------------

@dataclass
class EngineInputs:
    beneficiaries: list[engine.Beneficiary]
    visits: list[engine.Visit]
    doses: list[engine.DoseGiven]
    seeded_visits: set[tuple[str, str, date]]
    schedule: str = "hbnc2014"  # her visit schedule (D-32)

    def rules(self) -> list[dict]:
        return engine.load_ruleset(schedule=self.schedule)


def engine_inputs(db: Session, owner_id: str) -> EngineInputs:
    people = people_for(db, owner_id)
    bens = [engine.Beneficiary(p.id, p.category, p.dob, p.delivery_place, bool(p.at_risk)) for p in people if p.dob]
    visits, doses, seeded = [], [], set()
    table = dose_table()
    for n in db.scalars(select(Note).where(Note.owner_id == owner_id, Note.status == "confirmed")).all():
        r = n.confirmed
        bid, when = r["beneficiary"]["matched_id"], date.fromisoformat(r["visit_date"])
        idx = r["visit_index"]
        visits.append(engine.Visit(bid, r["visit_type"], when, idx.get("hbnc_day"), idx.get("hbyc_month"),
                                   any(d.get("present") for d in r["danger_signs"])))
        if n.source == "seed":
            seeded.add((bid, r["visit_type"], when))
        for s in r["services_given"]:
            did = dose_id(s.get("detail"), table) if s["type"] == "VACCINE" else None
            if did:
                doses.append(engine.DoseGiven(bid, did, when))
    return EngineInputs(bens, visits, doses, seeded, user_schedule(db, owner_id))


def list_tasks(db: Session, owner_id: str, today: date, lang: str) -> list[dict]:
    inp = engine_inputs(db, owner_id)
    people = {p.id: p for p in people_for(db, owner_id)}
    actions = {(a.beneficiary_id, a.rule_id): a for a in db.scalars(
        select(TaskAction).where(TaskAction.owner_id == owner_id)).all()}
    out = []
    for t in engine.open_tasks(engine.compute_tasks(inp.beneficiaries, inp.visits, inp.doses, today, inp.rules())):
        act = actions.get((t.beneficiary_id, t.rule_id))
        if act and (act.action == "dismiss" or (act.until and act.until > today)):
            continue
        p = people[t.beneficiary_id]
        out.append({"id": f"{t.beneficiary_id}:{t.rule_id}", "beneficiary_id": t.beneficiary_id,
                    "rule_id": t.rule_id, "programme": t.programme, "label": label(p, lang),
                    "due_date": t.due_date.isoformat(), "status": t.status,
                    "reason": t.reason_hi if lang == "hi" else t.reason_en, "advisory": t.advisory,
                    "area": p.area})
    return out


def label(p: NamePerson, lang: str) -> str:
    return (p.label_hi if lang == "hi" else p.label_en) or p.label_en or p.id


def form_context(db: Session, owner_id: str, person_id: str | None, lang: str) -> tuple[dict, str | None]:
    """Her saved details for the person a note is about, and the first date each vaccine dose appears in her
    CONFIRMED notes for that person (for the RCH child-tracking form). Returns (ctx, person category)."""
    people = {p.id: p for p in people_for(db, owner_id)}
    p = people.get(person_id or "")
    if p is None:
        return {}, None
    mother = people.get(p.mother_id or "")
    person = {"name": label(p, lang), "mother": label(mother, lang) if mother else None,
              "dob": p.dob.isoformat() if p.dob else None, "delivery_place": p.delivery_place, "area": p.area}
    table = dose_table()
    doses: dict[str, str] = {}
    for n in db.scalars(select(Note).where(Note.owner_id == owner_id, Note.status == "confirmed")).all():
        rec = n.confirmed or {}
        if (rec.get("beneficiary") or {}).get("matched_id") != p.id or not rec.get("visit_date"):
            continue
        for sv in rec.get("services_given") or []:
            did = dose_id(sv.get("detail"), table) if sv.get("type") == "VACCINE" else None
            if did and (did not in doses or rec["visit_date"] < doses[did]):
                doses[did] = rec["visit_date"]
    return {"person": person, "doses": doses}, p.category


def set_task_action(db: Session, owner_id: str, beneficiary_id: str, rule_id: str, action: str, until: date | None,
                    today: date) -> None:
    if action not in ("dismiss", "reschedule", "restore"):
        raise RequestError(422, "BAD_ACTION", "Unknown task action")
    existing = db.get(TaskAction, (owner_id, beneficiary_id, rule_id))
    if action == "restore":
        if existing:
            db.delete(existing)
    else:
        if action == "reschedule" and (until is None or until <= today):
            raise RequestError(422, "BAD_DATE", "Choose a later date")
        if existing:
            existing.action, existing.until = action, until
        else:
            db.add(TaskAction(owner_id=owner_id, beneficiary_id=beneficiary_id, rule_id=rule_id, action=action, until=until))
    db.add(AuditEvent(owner_id=owner_id, action=f"task_{action}", detail={"rule_id": rule_id}))
    db.commit()


# ---- synthetic demo data -------------------------------------------------------------------

_EXTRA_PEOPLE = [  # shown as completed history so the claim sheet has something to show
    {"id": "w20", "names": ["सीमा", "Seema"], "category": "other", "label_hi": "सीमा", "label_en": "Seema"},
    {"id": "c20", "names": [], "category": "newborn", "mother_id": "w20", "delivery_place": "institution",
     "label_hi": "सीमा की बच्ची", "label_en": "Baby girl of Seema"},
    {"id": "w21", "names": ["निशा", "Nisha"], "category": "other", "label_hi": "निशा", "label_en": "Nisha"},
    {"id": "c21", "names": ["रितु", "Ritu"], "category": "child", "mother_id": "w21", "label_hi": "रितु", "label_en": "Ritu"},
]
_FULL_HISTORY = {"c20", "c21"}
_GAPS = {("c08", "mr1")}  # left undone on purpose: an overdue vaccine for the demo story
_BIRTH_DOSES = {"bcg", "hepb0", "opv0"}


# The small demo (the default): six beneficiaries, each with a demo story.
#   c01 Sunita's newborn girl (HBNC starting) · c02 Rekha's newborn boy (home delivery)
#   c07 Anita's baby (HBNC midway)            · c08 Ishaan (MR-1 overdue)
#   c20 Seema's baby (HBNC complete → claim)  · w03 Pooja Yadav (pregnant)
# Mothers are added too so a note can name the baby through its mother ("Rekha's baby").
SMALL_DEMO = ("c01", "c02", "c07", "c08", "c20", "w03")
FULL_DEMO = None  # every person in the synthetic registry (eval and tests use it)


def _with_mothers(ids, all_people) -> set[str]:
    by_id = {p["id"] if isinstance(p, dict) else p.id: p for p in all_people}
    out = set(ids)
    for i in ids:
        p = by_id.get(i)
        mother = (p.get("mother_id") if isinstance(p, dict) else p.mother_id) if p else None
        if mother:
            out.add(mother)
    return out


def seed_demo(db: Session, owner_id: str, today: date, only: tuple[str, ...] | None = SMALL_DEMO) -> int:
    """Add invented people (and their demo visit history) that the ASHA does not already have.
    Birth dates shift with the calendar so the demo stays current. Returns people added."""
    shift = today - SEED_ANCHOR
    registry = load_people()
    keep = None if only is None else _with_mothers(only, [*registry, *_EXTRA_PEOPLE])
    have = {p.id for p in db.scalars(select(Person).where(Person.owner_id == owner_id)).all()}
    added: set[str] = set()
    for p in registry:
        if (keep is None or p.id in keep) and p.id not in have:
            db.add(Person(owner_id=owner_id, id=p.id, names=list(p.names), category=p.category, mother_id=p.mother_id,
                          dob=p.dob + shift if p.dob else None, delivery_place=p.delivery_place,
                          label_hi=p.label_hi, label_en=p.label_en, area=demo_area(p.id, p.mother_id)))
            added.add(p.id)
    extra_dob = {"c20": today - timedelta(days=45), "c21": add_months(today, -3) - timedelta(days=3)}
    for e in _EXTRA_PEOPLE:
        if (keep is None or e["id"] in keep) and e["id"] not in have:
            db.add(Person(owner_id=owner_id, dob=extra_dob.get(e["id"]), area=demo_area(e["id"], e.get("mother_id")), **e))
            added.add(e["id"])
    db.flush()

    people = {p.id: p for p in people_for(db, owner_id) if p.id in added}
    bens = [engine.Beneficiary(p.id, p.category, p.dob, p.delivery_place) for p in people.values() if p.dob]
    vaccines = {d["id"]: d["vaccine"] for d in load_yaml(RULES_DIR / "uip.yaml")["doses"]}
    recent = today - timedelta(days=7)
    grouped: dict[tuple[str, date], list[str]] = {}
    for t in engine.compute_tasks(bens, [], [], today):
        p = people[t.beneficiary_id]
        at_birth = t.rule_id in _BIRTH_DOSES and p.delivery_place == "institution"
        done = t.due_date <= (today if p.id in _FULL_HISTORY else recent) or (at_birth and t.due_date <= today)
        if (t.beneficiary_id, t.rule_id) in _GAPS or not done:
            continue
        if t.programme == "UIP":
            grouped.setdefault((t.beneficiary_id, t.due_date), []).append(vaccines[t.rule_id])
        else:
            m = re.fullmatch(r"hbnc_d(\d+)|hbyc_m(\d+)", t.rule_id)
            idx = {"hbnc_day": int(m[1])} if m[1] else {"hbyc_month": int(m[2])}
            db.add(_seed_note(owner_id, t.beneficiary_id, t.programme, t.due_date, idx, []))
    for (bid, when), names in grouped.items():
        db.add(_seed_note(owner_id, bid, "IMMUNIZATION", when, {}, names))
    db.commit()
    return len(added)


def _own_people(db: Session, owner_id: str) -> set[str]:
    """People the ASHA added herself or whose own notes (voice or typed, any status) refer to, plus their mothers."""
    ids: set[str] = {p.id for p in db.scalars(select(Person).where(Person.owner_id == owner_id)).all()
                     if p.id.startswith(OWN_PREFIX)}
    for n in db.scalars(select(Note).where(Note.owner_id == owner_id, Note.source != "seed")).all():
        for rec in (n.confirmed, n.draft):
            bid = ((rec or {}).get("beneficiary") or {}).get("matched_id")
            if bid:
                ids.add(bid)
    people = db.scalars(select(Person).where(Person.owner_id == owner_id)).all()
    return _with_mothers(ids, people)


def demo_status(db: Session, owner_id: str) -> dict:
    own = _own_people(db, owner_id)
    people = db.scalars(select(Person).where(Person.owner_id == owner_id)).all()
    notes = db.scalars(select(Note).where(Note.owner_id == owner_id, Note.source == "seed")).all()
    demo_people = [p for p in people if p.id not in own]
    return {"active": bool(demo_people or notes), "demo_people": len(demo_people), "demo_notes": len(notes),
            "beneficiaries": sum(1 for p in demo_people if p.id in SMALL_DEMO or p.category != "other")}


def remove_demo(db: Session, owner_id: str) -> dict:
    """Delete demo history and demo people. The ASHA's own notes, and the people they name, stay."""
    own = _own_people(db, owner_id)
    notes = db.scalars(select(Note).where(Note.owner_id == owner_id, Note.source == "seed")).all()
    for n in notes:
        db.delete(n)
    gone = [p.id for p in db.scalars(select(Person).where(Person.owner_id == owner_id)).all() if p.id not in own]
    if gone:
        db.execute(delete(Person).where(Person.owner_id == owner_id, Person.id.in_(gone)))
        db.execute(delete(TaskAction).where(TaskAction.owner_id == owner_id, TaskAction.beneficiary_id.in_(gone)))
    db.add(AuditEvent(owner_id=owner_id, action="demo_removed", detail={"people": len(gone), "notes": len(notes)}))
    db.commit()
    return demo_status(db, owner_id)


def load_demo(db: Session, owner_id: str, today: date) -> dict:
    added = seed_demo(db, owner_id, today, SMALL_DEMO)
    db.add(AuditEvent(owner_id=owner_id, action="demo_loaded", detail={"people": added}))
    db.commit()
    return demo_status(db, owner_id)


def _seed_note(owner_id: str, bid: str, vtype: str, when: date, idx: dict, vaccines: list[str]) -> Note:
    rec = VisitRecord(visit_type=vtype, visit_date=when, beneficiary={"matched_id": bid}, visit_index=idx,
                      services_given=[{"type": "VACCINE", "detail": v} for v in vaccines])
    return Note(owner_id=owner_id, status="confirmed", source="seed", recorded_on=when, transcript="",
                draft={}, confirmed=rec.model_dump(mode="json"), confirmed_at=datetime.combine(when, datetime.min.time()))


# ---- people the ASHA registers herself (T-045) ---------------------------------------------
# Ids start with "p-" so "Remove demo data" never touches them (demo ids are fixed, e.g. c01, w03).

OWN_PREFIX = "p-"
CATEGORIES = ("newborn", "child", "pregnant", "other")
MAX_NEWBORN_DAYS = 60   # HBNC runs to day 42; a little slack for late registration
MAX_CHILD_YEARS = 5
MAX_NAME = 60
MAX_AREA = 40
DEMO_AREAS = ("पूरब टोला", "पश्चिम टोला", "बाज़ार टोला")  # invented ward names (SIMULATED)


def _clean(name: str | None) -> str | None:
    name = " ".join((name or "").split())
    if len(name) > MAX_NAME:
        raise RequestError(422, "NAME_TOO_LONG", f"Keep the name under {MAX_NAME} characters", [{"path": "name"}])
    return name or None


def _clean_area(area: str | None) -> str | None:
    area = " ".join((area or "").split())
    if len(area) > MAX_AREA:
        raise RequestError(422, "AREA_TOO_LONG", f"Keep the area under {MAX_AREA} characters", [{"path": "area"}])
    return area or None


def demo_area(person_id: str, mother_id: str | None) -> str:
    """Stable invented area for demo people; a child lives where the mother lives."""
    root = mother_id or person_id
    return DEMO_AREAS[sum(map(ord, root)) % len(DEMO_AREAS)]


def _check_person(category: str, dob: date | None, today: date, delivery_place: str | None) -> None:
    if category not in CATEGORIES:
        raise RequestError(422, "BAD_CATEGORY", "Choose newborn, child, pregnant or other", [{"path": "category"}])
    if category in ("newborn", "child"):
        if dob is None:
            raise RequestError(422, "DOB_REQUIRED", "Date of birth is needed to work out visits and vaccines",
                               [{"path": "dob"}])
        if dob > today:
            raise RequestError(422, "DOB_IN_FUTURE", "Date of birth cannot be in the future", [{"path": "dob"}])
        age = (today - dob).days
        if category == "newborn" and age > MAX_NEWBORN_DAYS:
            raise RequestError(422, "NOT_NEWBORN", f"Older than {MAX_NEWBORN_DAYS} days: add as a child",
                               [{"path": "category"}])
        if category == "child" and age > MAX_CHILD_YEARS * 366:
            raise RequestError(422, "TOO_OLD", f"Children up to {MAX_CHILD_YEARS} years only", [{"path": "dob"}])
    if delivery_place not in (None, "home", "institution"):
        raise RequestError(422, "BAD_PLACE", "Birth place must be home or institution", [{"path": "delivery_place"}])


def add_person(db: Session, owner_id: str, today: date, *, name_hi: str | None, name_en: str | None, category: str,
               dob: date | None = None, mother_id: str | None = None, mother_name_hi: str | None = None,
               mother_name_en: str | None = None, delivery_place: str | None = None,
               area: str | None = None, at_risk: bool | None = None) -> Person:
    """Register a person. A newborn/child may be linked to an existing mother or to a new one added here;
    an unnamed newborn is labelled "<mother>'s baby" (that is also how notes name them)."""
    name_hi, name_en = _clean(name_hi), _clean(name_en)
    area = _clean_area(area)
    _check_person(category, dob, today, delivery_place)
    if category not in ("newborn", "child"):
        dob, delivery_place, mother_id, mother_name_hi, mother_name_en = None, None, None, None, None
    elif category == "child":
        delivery_place = None
    mother = None
    if mother_id:
        mother = db.get(Person, (owner_id, mother_id))
        if mother is None or mother.category in ("newborn", "child"):
            raise RequestError(422, "BAD_MOTHER", "Choose the mother from the list", [{"path": "mother_id"}])
    elif _clean(mother_name_hi) or _clean(mother_name_en):
        mother = add_person(db, owner_id, today, name_hi=mother_name_hi, name_en=mother_name_en, category="other",
                            area=area)
    if not (name_hi or name_en) and mother is None:
        raise RequestError(422, "NAME_REQUIRED", "Add a name (or the mother, for a newborn)", [{"path": "name"}])
    names = [n for n in (name_hi, name_en) if n]
    if names:
        label_hi, label_en = name_hi or name_en, name_en or name_hi
    else:
        label_hi = f"{mother.label_hi or mother.label_en} का बच्चा"
        label_en = f"{mother.label_en or mother.label_hi}'s baby"
    for p in db.scalars(select(Person).where(Person.owner_id == owner_id)).all():
        if (p.label_en == label_en and p.category == category and p.dob == dob
                and p.mother_id == (mother.id if mother else None)):
            raise RequestError(409, "PERSON_EXISTS", "This person is already in your list", [{"id": p.id}])
    person = Person(owner_id=owner_id, id=OWN_PREFIX + new_id()[:8], names=names, category=category,
                    mother_id=mother.id if mother else None, dob=dob, delivery_place=delivery_place,
                    label_hi=label_hi, label_en=label_en, area=area or (mother.area if mother else None),
                    at_risk=bool(at_risk) if category in ("newborn", "child") and at_risk is not None else None)
    db.add(person)
    db.add(AuditEvent(owner_id=owner_id, action="person_added", detail={"id": person.id, "category": category}))
    db.commit()
    return person


def update_person(db: Session, owner_id: str, person_id: str, today: date, *, name_hi: str | None,
                  name_en: str | None, dob: date | None, delivery_place: str | None,
                  area: str | None = None, at_risk: bool | None = None) -> Person:
    p = db.get(Person, (owner_id, person_id))
    if p is None or not p.id.startswith(OWN_PREFIX):
        raise RequestError(404, "NOT_FOUND", "Only people you added can be edited")
    name_hi, name_en = _clean(name_hi), _clean(name_en)
    if p.category in ("newborn", "child"):
        _check_person(p.category, dob, today, delivery_place if p.category == "newborn" else None)
        p.dob, p.delivery_place = dob, delivery_place if p.category == "newborn" else None
    if name_hi or name_en:
        p.names = [n for n in (name_hi, name_en) if n]
        p.label_hi, p.label_en = name_hi or name_en, name_en or name_hi
    if area is not None:  # "" clears it, None leaves it
        p.area = _clean_area(area)
    if at_risk is not None and p.category in ("newborn", "child"):
        p.at_risk = at_risk
    db.add(AuditEvent(owner_id=owner_id, action="person_updated", detail={"id": p.id}))
    db.commit()
    return p


def delete_person(db: Session, owner_id: str, person_id: str) -> None:
    p = db.get(Person, (owner_id, person_id))
    if p is None or not p.id.startswith(OWN_PREFIX):
        raise RequestError(404, "NOT_FOUND", "Only people you added can be removed")
    used = any(((rec or {}).get("beneficiary") or {}).get("matched_id") == person_id
               for n in db.scalars(select(Note).where(Note.owner_id == owner_id)).all()
               for rec in (n.draft, n.confirmed))
    kids = db.scalars(select(Person).where(Person.owner_id == owner_id, Person.mother_id == person_id)).first()
    if used or kids:
        raise RequestError(409, "PERSON_IN_USE", "This person has notes or children recorded and cannot be removed")
    db.delete(p)
    db.execute(delete(TaskAction).where(TaskAction.owner_id == owner_id, TaskAction.beneficiary_id == person_id))
    db.add(AuditEvent(owner_id=owner_id, action="person_removed", detail={"id": person_id}))
    db.commit()


def wipe_owner_data(db: Session, owner_id: str, today: date) -> int:
    notes = db.scalars(select(Note).where(Note.owner_id == owner_id)).all()
    for n in notes:
        delete_audio(n)
    count = len(notes)
    for model in (Note, TaskAction, AuditEvent, Person):
        db.execute(delete(model).where(model.owner_id == owner_id))
    db.commit()
    seed_demo(db, owner_id, today)
    return count


def edit_stats(db: Session, owner_id: str, year: int, month: int) -> dict:
    """How often the ASHA had to correct each field before confirming (her own notes, this month).
    It measures the *extractor*, not her: it shows where A.U.R.A. mishears. Demo notes are excluded."""
    start = date(year, month, 1)
    end = add_months(start, 1)
    notes = [n for n in db.scalars(select(Note).where(Note.owner_id == owner_id, Note.status == "confirmed",
                                                      Note.source != "seed")).all()
             if start <= n.recorded_on < end]
    counts: dict[str, int] = {}
    for n in notes:
        for p in set(n.edited_paths or []):
            counts[p] = counts.get(p, 0) + 1
    fields = sorted(({"path": p, "edited": c} for p, c in counts.items()), key=lambda r: (-r["edited"], r["path"]))
    return {"month": f"{year:04d}-{month:02d}", "notes": len(notes),
            "unchanged": sum(1 for n in notes if not n.edited_paths), "fields": fields}
