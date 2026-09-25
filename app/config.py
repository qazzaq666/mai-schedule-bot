from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class Settings:
    bot_token: str
    db_path: str = "bot.db"
    cache_ttl_seconds: int = 900
    semester_start: date | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN не задан в .env")

        raw_start = os.getenv("SEMESTER_START", "").strip()
        semester_start = date.fromisoformat(raw_start) if raw_start else None

        return cls(
            bot_token=token,
            db_path=os.getenv("DB_PATH", "bot.db"),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "900")),
            semester_start=semester_start,
        )
