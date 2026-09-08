"""SQLAlchemy ORM models for users, sessions, statement revisions, and analysis snapshots.

Kept separate from the plain Pydantic contracts in core/ (StatementRevision, AnalysisResult):
these are the persisted rows; core/ contracts are the storage-independent shapes they are
read into and validated against at the API boundary.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from yaounde_analyzer.core.scope import TARGET_VARIETY


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime]


class AuthSession(Base):
    """A revocable login session. Only the SHA-256 hash of the bearer token is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]

    user: Mapped[User] = relationship()


class StatementRecord(Base):
    """A logical statement's identity and its currently published (approved-public) revision."""

    __tablename__ = "statement_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    published_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("statement_revisions.id", use_alter=True), nullable=True
    )

    revisions: Mapped[list[StatementRevisionRow]] = relationship(
        back_populates="record",
        order_by="StatementRevisionRow.revision",
        foreign_keys="StatementRevisionRow.record_id",
    )
    published_revision: Mapped[StatementRevisionRow | None] = relationship(
        foreign_keys=[published_revision_id], post_update=True
    )


class StatementRevisionRow(Base):
    """One immutable, append-only revision of a statement."""

    __tablename__ = "statement_revisions"
    __table_args__ = (UniqueConstraint("record_id", "revision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("statement_records.id"))
    revision: Mapped[int]
    source_kind: Mapped[str] = mapped_column(String(16))
    raw_text: Mapped[str] = mapped_column(Text)
    manual_transcription_attested: Mapped[bool]
    collector_id: Mapped[str] = mapped_column(String(64))
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    target_variety: Mapped[str] = mapped_column(String(32), default=TARGET_VARIETY)
    created_at: Mapped[datetime]
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    record: Mapped[StatementRecord] = relationship(
        back_populates="revisions", foreign_keys=[record_id]
    )
    created_by_user: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])


class AnalysisSnapshotRow(Base):
    """A persisted analysis result tied to one exact statement revision."""

    __tablename__ = "analysis_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("statement_revisions.id"))
    analyzer_version: Mapped[str] = mapped_column(String(64))
    spec_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime]
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    revision: Mapped[StatementRevisionRow] = relationship()
