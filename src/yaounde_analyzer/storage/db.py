"""A testable database wrapper: one instance per app or test, no module-level globals."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from yaounde_analyzer.storage.models import Base


@dataclass
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def create(cls, database_url: str) -> Database:
        engine_kwargs: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in database_url:
                # A single shared connection, or every session sees its own empty database.
                engine_kwargs["poolclass"] = StaticPool
        engine = create_engine(database_url, **engine_kwargs)
        session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        return cls(engine=engine, session_factory=session_factory)

    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session_scope(self) -> Iterator[Session]:
        """FastAPI dependency generator: one session per request, always closed."""
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()
