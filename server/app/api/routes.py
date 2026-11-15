"""HTTP API (/v1). Consistent error shape: {"error": {"code", "message", "details"}}."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import RULES_DIR, load_yaml
from ..core.settings import Settings
from ..db.models import AuditEvent, Note, Otp, TaskAction, User, utcnow
from ..reports import monthly
from ..reports.claims import claim_sheet
from ..reports.export import to_pdf, to_xlsx
from ..services import (
    RequestError,
    TaskHint,
    confirm_note,
    create_note,
    delete_audio,
    demo_status,
    engine_inputs,
    label,
    list_tasks,
    load_demo,
    people_for,
    remove_demo,
    seed_demo,
    set_task_action,
    wipe_owner_data,
)
from ..stt.base import NotConfigured, SttError, wav_info

router = APIRouter(prefix="/v1")

MAX_AUDIO_BYTES = 12 * 1024 * 1024
MAX_AUDIO_SECONDS = 180
MAX_TEXT_CHARS = 2000
OTP_ATTEMPTS = 5
TOKEN_DAYS = 30


def settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    db = request.app.state.sessions()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise RequestError(401, "UNAUTHENTICATED", "Please log in")
    try:
        claims = jwt.decode(authorization[7:], request.app.state.settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise RequestError(401, "UNAUTHENTICATED", "Please log in again") from exc
    user = db.get(User, claims.get("sub"))
    if user is None:
        raise RequestError(401, "UNAUTHENTICATED", "Please log in again")
    return user


def user_view(u: User) -> dict:
    return {"id": u.id, "phone": u.phone, "asha_id": u.asha_id, "name": u.name, "lang": u.lang}


def own_note(db: Session, user: User, note_id: str) -> Note:
    note = db.get(Note, note_id)
    if note is None or note.owner_id != user.id:
        raise RequestError(404, "NOT_FOUND", "Note not found")
    return note


def note_view(n: Note, db: Session, lang: str, **extra) -> dict:
    people = {p.id: p for p in people_for(db, n.owner_id)}
    return {"id": n.id, "status": n.status, "source": n.source, "language": n.language,
            "recorded_on": n.recorded_on.isoformat(), "transcript": n.transcript, "stt_provider": n.stt_provider,
            "stt_confidence": n.stt_confidence, "record": n.confirmed or n.draft, "flags": n.flags,
            "candidates": [{"id": c, "label": label(people[c], lang)} for c in n.candidates if c in people],
            "has_audio": bool(n.audio_path), "edited_paths": n.edited_paths,
            "created_at": n.created_at.isoformat() + "Z", **extra}


# ---- meta and auth --------------------------------------------------------------------------

@router.get("/meta")
def meta(request: Request) -> dict:
    stt = request.app.state.stt_status()
    v = load_yaml(RULES_DIR / "validation.yaml")
    return {"stt": stt, "extractor": "rule-based-v0",
            "danger_signs": v["danger_signs"],
            "vaccines": [d["vaccine"] for d in load_yaml(RULES_DIR / "uip.yaml")["doses"]],
            "rules_status": {n: load_yaml(RULES_DIR / f"{n}.yaml")["status"] for n in ("hbnc", "hbyc", "uip")},
            "simulated": ["login_otp", "demo_history"], "data": "synthetic"}


class OtpRequest(BaseModel):
    phone: str


class OtpVerify(BaseModel):
    phone: str
    otp: str
    asha_id: str | None = None
    name: str | None = None
    lang: str | None = None


def _phone(raw: str) -> str:
    phone = re.sub(r"\D", "", raw)[-10:]
    if not re.fullmatch(r"[6-9]\d{9}", phone):
        raise RequestError(422, "BAD_PHONE", "Enter a 10-digit mobile number")
    return phone


@router.post("/auth/otp/request")
def otp_request(body: OtpRequest, db: Session = Depends(get_db)) -> dict:
    phone = _phone(body.phone)
    code = f"{secrets.randbelow(1000000):06d}"
    row = db.get(Otp, phone)
    expires = utcnow() + timedelta(minutes=5)
    if row:
        row.code, row.expires_at, row.attempts = code, expires, 0
    else:
        db.add(Otp(phone=phone, code=code, expires_at=expires, attempts=0))
    db.commit()
    return {"simulated": True, "otp": code}  # SIMULATED: no SMS provider; the code is shown on screen


@router.post("/auth/otp/verify")
def otp_verify(body: OtpVerify, request: Request, db: Session = Depends(get_db)) -> dict:
    cfg = settings(request)
    phone = _phone(body.phone)
    row = db.get(Otp, phone)
    if row is None or row.expires_at < utcnow() or row.attempts >= OTP_ATTEMPTS:
        raise RequestError(401, "OTP_EXPIRED", "Code expired. Request a new one")
    if not secrets.compare_digest(row.code, body.otp.strip()):
        row.attempts += 1
        db.commit()
        raise RequestError(401, "OTP_WRONG", "Wrong code")
    db.delete(row)
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, lang=body.lang if body.lang in ("hi", "en") else "hi")
        db.add(user)
        db.flush()
        seed_demo(db, user.id, cfg.today())
    user.asha_id = (body.asha_id or user.asha_id or "").strip() or None
    user.name = (body.name or user.name or "").strip() or None
    db.commit()
    token = jwt.encode({"sub": user.id, "exp": datetime.now(UTC) + timedelta(days=TOKEN_DAYS)}, cfg.jwt_secret, algorithm="HS256")
    return {"token": token, "user": user_view(user), "simulated": True}


class Profile(BaseModel):
    asha_id: str | None = None
    name: str | None = None
    lang: str | None = None


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return user_view(user)


@router.patch("/me")
def update_me(body: Profile, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if body.lang is not None:
        if body.lang not in ("hi", "en"):
            raise RequestError(422, "BAD_LANGUAGE", "Language must be hi or en")
        user.lang = body.lang
    if body.asha_id is not None:
        user.asha_id = body.asha_id.strip() or None
    if body.name is not None:
        user.name = body.name.strip() or None
    db.merge(user)
    db.commit()
    return user_view(user)


@router.get("/beneficiaries")
def beneficiaries(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = [{"id": p.id, "label": label(p, user.lang), "category": p.category} for p in people_for(db, user.id)]
    return sorted(rows, key=lambda r: r["label"])


# ---- notes ----------------------------------------------------------------------------------

@router.post("/notes", status_code=201)
def post_note(request: Request, audio: UploadFile | None = File(default=None), text: str | None = Form(default=None),
              language: str = Form(default="hi"), idempotency_key: str | None = Form(default=None),
              beneficiary_id: str | None = Form(default=None), programme: str | None = Form(default=None),
              rule_id: str | None = Form(default=None), recorded_on: str | None = Form(default=None),
              user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if language not in ("hi", "en"):
        raise RequestError(422, "BAD_LANGUAGE", "Language must be hi or en")
    spoken_on = _recorded_on(recorded_on, settings(request).today())
    typed = (text or "").strip()
    if (audio is None) == (not typed):
        raise RequestError(422, "NEED_ONE_INPUT", "Send either audio or text")
    if len(typed) > MAX_TEXT_CHARS:
        raise RequestError(422, "TEXT_TOO_LONG", "This note is too long")
    wav, stt = None, None
    if audio is not None:
        wav = audio.file.read(MAX_AUDIO_BYTES + 1)
        if len(wav) > MAX_AUDIO_BYTES:
            raise RequestError(413, "AUDIO_TOO_LARGE", "This recording is too large")
        try:
            duration = wav_info(wav)[3]
            if duration > MAX_AUDIO_SECONDS:
                raise RequestError(413, "AUDIO_TOO_LONG", "Keep a note under 3 minutes")
            stt = request.app.state.get_stt()
        except NotConfigured as exc:
            raise RequestError(503, "STT_UNAVAILABLE", str(exc)) from exc
        except SttError as exc:
            raise RequestError(415, "BAD_AUDIO", str(exc)) from exc
    try:
        note = create_note(db, settings(request), stt, user.id, text=typed, wav=wav, language=language,
                           hint=TaskHint(beneficiary_id, programme, rule_id), idempotency_key=idempotency_key,
                           recorded_on=spoken_on)
    except SttError as exc:
        raise RequestError(503, "STT_FAILED", str(exc)) from exc
    return note_view(note, db, user.lang)


MAX_QUEUE_DAYS = 60


def _recorded_on(raw: str | None, today: date) -> date:
    """Date the note was spoken on the phone. A note queued offline keeps its own date, so "aaj"/"kal"
    resolve against the day of the visit, not the day it reached the server."""
    if not raw:
        return today
    try:
        when = date.fromisoformat(raw)
    except ValueError as exc:
        raise RequestError(422, "BAD_RECORDED_ON", "recorded_on must be YYYY-MM-DD") from exc
    if when > today:  # phone clock ahead (or a different time zone): never allow future dates
        return today
    if (today - when).days > MAX_QUEUE_DAYS:
        raise RequestError(422, "RECORDED_ON_TOO_OLD", f"Notes older than {MAX_QUEUE_DAYS} days cannot be added")
    return when


@router.get("/notes")
def get_notes(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    q = select(Note).where(Note.owner_id == user.id, Note.source != "seed").order_by(Note.created_at.desc()).limit(100)
    if status:
        q = q.where(Note.status == status)
    return [note_view(n, db, user.lang) for n in db.scalars(q).all()]


@router.get("/notes/{note_id}")
def get_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return note_view(own_note(db, user, note_id), db, user.lang)


@router.get("/notes/{note_id}/audio")
def get_audio(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    note = own_note(db, user, note_id)
    if not note.audio_path or not Path(note.audio_path).exists():
        raise RequestError(404, "NO_AUDIO", "Audio is not available")
    return Response(Path(note.audio_path).read_bytes(), media_type="audio/wav")


class ConfirmBody(BaseModel):
    record: dict


@router.post("/notes/{note_id}/confirm")
def post_confirm(note_id: str, body: ConfirmBody, request: Request, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    note, audio_deleted = confirm_note(db, settings(request), own_note(db, user, note_id), body.record)
    return note_view(note, db, user.lang, audio_deleted=audio_deleted)


@router.post("/notes/{note_id}/discard")
def post_discard(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    note = own_note(db, user, note_id)
    if note.status == "confirmed":
        raise RequestError(409, "ALREADY_CONFIRMED", "A confirmed note cannot be discarded here")
    note.status = "discarded"
    delete_audio(note)
    db.add(AuditEvent(owner_id=user.id, note_id=note.id, action="discarded", detail={}))
    db.commit()
    return {"id": note.id, "status": note.status}


# ---- tasks and reports ----------------------------------------------------------------------

@router.get("/tasks")
def get_tasks(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    return list_tasks(db, user.id, settings(request).today(), user.lang)


class TaskActionBody(BaseModel):
    action: str
    until: date | None = None


@router.post("/tasks/{beneficiary_id}/{rule_id}/action")
def post_task_action(beneficiary_id: str, rule_id: str, body: TaskActionBody, request: Request,
                     user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    set_task_action(db, user.id, beneficiary_id, rule_id, body.action, body.until, settings(request).today())
    return {"ok": True}


@router.get("/reports/claims", response_model=None)
def get_claims(request: Request, month: str | None = None, format: str = "json", lang: str | None = None,
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = settings(request).today()
    m = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", month or today.strftime("%Y-%m"))
    if not m:
        raise RequestError(422, "BAD_MONTH", "Month must look like 2026-11")
    use_lang = lang if lang in ("hi", "en") else user.lang
    sheet = claim_sheet(people_for(db, user.id), engine_inputs(db, user.id), today, int(m[1]), int(m[2]), use_lang)
    name = f"claim-support-{sheet['month']}"
    if format == "pdf":
        return Response(to_pdf(sheet, user_view(user), use_lang), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
    if format == "xlsx":
        return Response(to_xlsx(sheet, user_view(user), use_lang),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    if format != "json":
        raise RequestError(422, "BAD_FORMAT", "Format must be json, pdf or xlsx")
    return sheet


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/reports/monthly", response_model=None)
def get_monthly(request: Request, month: str | None = None, format: str = "json", lang: str | None = None,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Monthly report: confirmed visits, summary, open tasks and incentive claim support."""
    today = settings(request).today()
    m = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", month or today.strftime("%Y-%m"))
    if not m:
        raise RequestError(422, "BAD_MONTH", "Month must look like 2026-11")
    if format not in ("json", "pdf", "xlsx"):
        raise RequestError(422, "BAD_FORMAT", "Format must be json, pdf or xlsx")
    use_lang = lang if lang in ("hi", "en") else user.lang
    people, inputs = people_for(db, user.id), engine_inputs(db, user.id)
    year, mon = int(m[1]), int(m[2])
    claim = claim_sheet(people, inputs, today, year, mon, use_lang)
    rep = monthly.build(db, user.id, people, inputs, claim, today, year, mon, use_lang)
    name = f"aura-monthly-report-{rep['month']}"
    if format == "pdf":
        return Response(monthly.to_pdf(rep, user_view(user)), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
    if format == "xlsx":
        return Response(monthly.to_xlsx(rep, user_view(user)), media_type=XLSX,
                        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    return rep


# ---- demo data (SIMULATED) -------------------------------------------------------------------

class DemoBody(BaseModel):
    action: str  # remove | load


@router.get("/demo")
def get_demo(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return demo_status(db, user.id)


@router.post("/demo")
def post_demo(body: DemoBody, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Remove the invented demo people and history, or load the small demo set (6 beneficiaries)."""
    if body.action == "remove":
        return remove_demo(db, user.id)
    if body.action == "load":
        return load_demo(db, user.id, settings(request).today())
    raise RequestError(422, "BAD_ACTION", "Action must be remove or load")


# ---- privacy --------------------------------------------------------------------------------

@router.get("/privacy/summary")
def privacy_summary(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    def count(*where) -> int:
        return db.scalar(select(func.count()).select_from(Note).where(Note.owner_id == user.id, *where)) or 0

    return {"confirmed_notes": count(Note.status == "confirmed", Note.source != "seed"),
            "draft_notes": count(Note.status == "draft"),
            "demo_history_notes": count(Note.source == "seed"),
            "audio_files": count(Note.audio_path.is_not(None)),
            "audit_events": db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.owner_id == user.id)) or 0,
            "never_collected": ["location", "contacts", "call_logs", "sms", "other_apps", "attendance", "productivity"]}


@router.get("/privacy/export")
def privacy_export(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    notes = db.scalars(select(Note).where(Note.owner_id == user.id, Note.source != "seed")).all()
    from fastapi.responses import JSONResponse

    return JSONResponse({"profile": user_view(user), "notes": [note_view(n, db, user.lang) for n in notes],
                         "task_actions": [{"beneficiary_id": a.beneficiary_id, "rule_id": a.rule_id, "action": a.action,
                                           "until": a.until.isoformat() if a.until else None} for a in db.scalars(
                                               select(TaskAction).where(TaskAction.owner_id == user.id)).all()]},
                        headers={"Content-Disposition": 'attachment; filename="aura-export.json"'})


@router.delete("/privacy/data")
def privacy_delete(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    wipe_owner_data(db, user.id, settings(request).today())
    return {"ok": True}
