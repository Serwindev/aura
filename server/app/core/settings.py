"""Runtime settings from the environment. Nothing here is a secret by default: JWT_SECRET is
generated once per install and kept in the (git-ignored) data directory."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    data_dir: Path
    database_url: str
    jwt_secret: str
    stt_provider: str = "vosk"
    audio_retention_hours: int = 168
    today_override: date | None = None  # tests and rehearsals only

    def today(self) -> date:
        return self.today_override or date.today()

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


def _jwt_secret(data_dir: Path) -> str:
    env = os.environ.get("JWT_SECRET")
    if env and env != "change-me":
        return env
    path = data_dir / "jwt.secret"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def load_settings(data_dir: Path | None = None) -> Settings:
    root = data_dir or Path(os.environ.get("AURA_DATA_DIR") or SERVER_DIR / "data")
    root.mkdir(parents=True, exist_ok=True)
    override = os.environ.get("AURA_TODAY")
    return Settings(
        data_dir=root,
        database_url=os.environ.get("DATABASE_URL") or f"sqlite:///{(root / 'aura.db').as_posix()}",
        jwt_secret=_jwt_secret(root),
        stt_provider=os.environ.get("STT_PROVIDER") or "vosk",
        audio_retention_hours=int(os.environ.get("AUDIO_RETENTION_HOURS") or 168),
        today_override=date.fromisoformat(override) if override else None,
    )
