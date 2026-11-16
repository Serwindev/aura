"""SQLAlchemy models (SQLite for the prototype, D-13). Confirmed notes are the single source of
truth: visits and doses are derived from them, so there is nothing to keep in sync."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    phone: Mapped[str] = mapped_column(String, unique=True)
    asha_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    lang: Mapped[str] = mapped_column(String, default="hi")
    schedule: Mapped[str | None] = mapped_column(String, nullable=True)  # visit schedule (D-32); None = 2014 default
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Otp(Base):
    """SIMULATED login: the code is shown on screen, no SMS is sent."""

    __tablename__ = "otps"
    phone: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class Person(Base):
    __tablename__ = "people"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    names: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String)
    mother_id: Mapped[str | None] = mapped_column(String, nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_place: Mapped[str | None] = mapped_column(String, nullable=True)
    label_hi: Mapped[str | None] = mapped_column(String, nullable=True)
    label_en: Mapped[str | None] = mapped_column(String, nullable=True)
    area: Mapped[str | None] = mapped_column(String, nullable=True)  # ward/tola/village she groups visits by (no GPS)
    at_risk: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # she marked an 'at-risk' newborn (SSBSK)
    # form details kept on the person (asked once, reused by every form; D-39)
    sex: Mapped[str | None] = mapped_column(String, nullable=True)  # male | female
    birth_weight_kg: Mapped[float | None] = mapped_column(nullable=True)
    rch_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | confirmed | discarded
    source: Mapped[str] = mapped_column(String)  # audio | text | seed
    language: Mapped[str] = mapped_column(String, default="hi")
    recorded_on: Mapped[date] = mapped_column(Date)
    transcript: Mapped[str] = mapped_column(Text, default="")
    stt_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    stt_confidence: Mapped[float | None] = mapped_column(nullable=True)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    confirmed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edited_paths: Mapped[list] = mapped_column(JSON, default=list)
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TaskAction(Base):
    __tablename__ = "task_actions"
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    beneficiary_id: Mapped[str] = mapped_column(String, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    action: Mapped[str] = mapped_column(String)  # dismiss | reschedule
    until: Mapped[date | None] = mapped_column(Date, nullable=True)


class AuditEvent(Base):
    """Which fields changed, never their values (no PII in the audit trail)."""

    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String, index=True)
    note_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def make_session_factory(url: str) -> sessionmaker:
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=args)
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    return sessionmaker(engine, expire_on_commit=False)


# Columns added after v1.0. create_all() does not alter existing tables, so add them here (additive only).
_LATER_COLUMNS = {"people": {"area": "VARCHAR", "at_risk": "BOOLEAN", "sex": "VARCHAR", "birth_weight_kg": "FLOAT",
                             "rch_id": "VARCHAR"}, "users": {"schedule": "VARCHAR"}}


def _add_missing_columns(engine) -> None:
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _LATER_COLUMNS.items():
            have = {c["name"] for c in insp.get_columns(table)}
            for name, sqltype in cols.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"))
