"""Runtime configuration, read from environment variables with safe local-dev defaults.

`cookie_secure` must be True in any real deployment (HTTPS behind Nginx, per the plan's
Phase 4). It defaults to False only so the app is usable over plain http on localhost
during development; this is flagged here rather than silently left insecure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    cookie_secure: bool
    session_lifetime_seconds: int
    max_anonymous_text_characters: int
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5175", "http://localhost:5175")

    @classmethod
    def from_env(cls) -> Settings:
        cors_origins = tuple(
            origin.strip()
            for origin in os.environ.get(
                "YAOUNDE_CORS_ORIGINS", "http://127.0.0.1:5175,http://localhost:5175"
            ).split(",")
            if origin.strip()
        )
        return cls(
            database_url=os.environ.get("YAOUNDE_DATABASE_URL", "sqlite:///./data/app.db"),
            cookie_secure=os.environ.get("YAOUNDE_ENV", "development") == "production",
            session_lifetime_seconds=int(os.environ.get("YAOUNDE_SESSION_SECONDS", 8 * 3600)),
            max_anonymous_text_characters=int(os.environ.get("YAOUNDE_MAX_TEXT_CHARS", 2000)),
            cors_origins=cors_origins,
        )
