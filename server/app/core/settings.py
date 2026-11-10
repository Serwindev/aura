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
    stt_provider: str = "auto"
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


def load_dotenv(path: Path = SERVER_DIR / ".env") -> None:
    """Read KEY=VALUE lines from server/.env into the environment, never overriding a variable
    that is already set. Values are never logged."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def load_settings(data_dir: Path | None = None) -> Settings:
    load_dotenv()
    root = data_dir or Path(os.environ.get("AURA_DATA_DIR") or SERVER_DIR / "data")
    root.mkdir(parents=True, exist_ok=True)
    override = os.environ.get("AURA_TODAY")
    return Settings(
        data_dir=root,
        database_url=os.environ.get("DATABASE_URL") or f"sqlite:///{(root / 'aura.db').as_posix()}",
        jwt_secret=_jwt_secret(root),
        stt_provider=os.environ.get("STT_PROVIDER") or "auto",
        audio_retention_hours=int(os.environ.get("AUDIO_RETENTION_HOURS") or 168),
        today_override=date.fromisoformat(override) if override else None,
    )
