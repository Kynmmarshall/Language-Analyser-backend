"""Data access functions for users, sessions, statement revisions, and analysis snapshots.

Revision writes are optimistic-concurrency checked: callers must pass the revision they
last saw, and a stale write raises RevisionConflictError rather than silently overwriting
a concurrent edit.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from yaounde_analyzer.api.security import generate_token, hash_password, hash_token, verify_password
from yaounde_analyzer.core.corpus import utc_now
from yaounde_analyzer.core.scope import TARGET_VARIETY
from yaounde_analyzer.storage.models import (
    AnalysisSnapshotRow,
    AuthSession,
    StatementRecord,
    StatementRevisionRow,
    User,
)


def _now() -> datetime:
    """Naive UTC now, for storage and comparison.

    SQLite has no native timezone-aware datetime type: values written as aware
    datetimes come back naive on read, so comparing them against a fresh aware
    `utc_now()` raises. Storing and comparing naive UTC everywhere avoids that
    mismatch; every value here is UTC by convention, never local time.
    """
    return utc_now().replace(tzinfo=None)


class RevisionConflictError(ValueError):
    """Raised when a write's expected_revision does not match the current latest revision."""


class DuplicateStatementError(ValueError):
    """Raised when creating a statement_id that already exists."""


class StatementNotFoundError(ValueError):
    pass


# --- Users -------------------------------------------------------------------------------


def create_user(session: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password), created_at=_now())
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username))


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


# --- Sessions ----------------------------------------------------------------------------


def create_auth_session(
    session: Session, user: User, lifetime_seconds: int
) -> tuple[AuthSession, str, str]:
    """Returns (row, raw_session_token, csrf_token); only the row's hash is persisted."""
    raw_token = generate_token()
    csrf_token = generate_token()
    now = _now()
    row = AuthSession(
        token_hash=hash_token(raw_token),
        csrf_token=csrf_token,
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(seconds=lifetime_seconds),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, raw_token, csrf_token


def get_valid_auth_session(session: Session, raw_token: str) -> AuthSession | None:
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token)))
    if row is None or row.expires_at <= _now():
        return None
    return row


def revoke_auth_session(session: Session, raw_token: str) -> None:
    row = session.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token)))
    if row is not None:
        session.delete(row)
        session.commit()


# --- Statements ----------------------------------------------------------------------------


def topics_to_json(topics: tuple[str, ...]) -> str:
    return json.dumps(list(topics))


def topics_from_json(payload: str) -> tuple[str, ...]:
    return tuple(json.loads(payload))


def create_statement(
    session: Session,
    *,
    statement_id: str,
    source_kind: str,
    raw_text: str,
    manual_transcription_attested: bool,
    collector_id: str,
    topics: tuple[str, ...],
    created_by_user_id: int | None,
    target_variety: str = TARGET_VARIETY,
) -> StatementRevisionRow:
    existing = session.scalar(
        select(StatementRecord).where(StatementRecord.statement_id == statement_id)
    )
    if existing is not None:
        raise DuplicateStatementError(f"statement_id {statement_id!r} already exists")

    record = StatementRecord(statement_id=statement_id)
    session.add(record)
    session.flush()  # assign record.id without committing yet

    revision_row = StatementRevisionRow(
        record_id=record.id,
        revision=1,
        source_kind=source_kind,
        raw_text=raw_text,
        manual_transcription_attested=manual_transcription_attested,
        collector_id=collector_id,
        topics_json=topics_to_json(topics),
        target_variety=target_variety,
        created_at=_now(),
        created_by_user_id=created_by_user_id,
    )
    session.add(revision_row)
    session.commit()
    session.refresh(revision_row)
    return revision_row


def add_statement_revision(
    session: Session,
    *,
    statement_id: str,
    expected_revision: int,
    raw_text: str,
    source_kind: str,
    manual_transcription_attested: bool,
    collector_id: str,
    topics: tuple[str, ...],
    created_by_user_id: int | None,
) -> StatementRevisionRow:
    record = session.scalar(
        select(StatementRecord).where(StatementRecord.statement_id == statement_id)
    )
    if record is None:
        raise StatementNotFoundError(f"statement_id {statement_id!r} does not exist")

    latest = max((r.revision for r in record.revisions), default=0)
    if latest != expected_revision:
        raise RevisionConflictError(
            f"expected revision {expected_revision} but the latest is {latest}; "
            "reload the statement before editing again"
        )

    new_row = StatementRevisionRow(
        record_id=record.id,
        revision=latest + 1,
        source_kind=source_kind,
        raw_text=raw_text,
        manual_transcription_attested=manual_transcription_attested,
        collector_id=collector_id,
        topics_json=topics_to_json(topics),
        created_at=_now(),
        created_by_user_id=created_by_user_id,
    )
    # Public approval is tied to one exact reviewed wording; any edit needs fresh review.
    record.published_revision_id = None
    session.add(new_row)
    session.commit()
    session.refresh(new_row)
    return new_row


def get_statement_record(session: Session, statement_id: str) -> StatementRecord | None:
    return session.scalar(
        select(StatementRecord).where(StatementRecord.statement_id == statement_id)
    )


def list_statement_records(session: Session) -> list[StatementRecord]:
    return list(session.scalars(select(StatementRecord)).all())


def publish_revision(session: Session, statement_id: str, revision: int) -> StatementRevisionRow:
    record = get_statement_record(session, statement_id)
    if record is None:
        raise StatementNotFoundError(f"statement_id {statement_id!r} does not exist")
    target = next((r for r in record.revisions if r.revision == revision), None)
    if target is None:
        raise StatementNotFoundError(f"revision {revision} of {statement_id!r} does not exist")
    record.published_revision_id = target.id
    session.commit()
    return target


def unpublish(session: Session, statement_id: str) -> None:
    record = get_statement_record(session, statement_id)
    if record is None:
        raise StatementNotFoundError(f"statement_id {statement_id!r} does not exist")
    record.published_revision_id = None
    session.commit()


# --- Analysis snapshots ----------------------------------------------------------------


def save_analysis_snapshot(
    session: Session,
    *,
    snapshot_id: str,
    revision_id: int,
    analyzer_version: str,
    spec_hash: str,
    result_json: str,
    created_by_user_id: int | None,
) -> AnalysisSnapshotRow:
    row = AnalysisSnapshotRow(
        snapshot_id=snapshot_id,
        revision_id=revision_id,
        analyzer_version=analyzer_version,
        spec_hash=spec_hash,
        result_json=result_json,
        created_at=_now(),
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
