"""Protected corpus CRUD, revision history, publish/unpublish, and the public examples list."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from yaounde_analyzer.api.deps import get_db, require_csrf, require_user
from yaounde_analyzer.api.repository import (
    DuplicateStatementError,
    RevisionConflictError,
    StatementNotFoundError,
    add_statement_revision,
    create_statement,
    get_statement_record,
    list_statement_records,
    publish_revision,
    topics_from_json,
    unpublish,
)
from yaounde_analyzer.api.schemas import (
    PublishRequest,
    StatementCreateRequest,
    StatementPrivate,
    StatementPublic,
    StatementRevisionHistoryItem,
    StatementUpdateRequest,
)
from yaounde_analyzer.storage.models import StatementRecord, StatementRevisionRow, User

router = APIRouter(prefix="/api", tags=["corpus"])


def _to_private(record: StatementRecord) -> StatementPrivate:
    latest = record.revisions[-1]
    published_revision = (
        record.published_revision.revision if record.published_revision is not None else None
    )
    return StatementPrivate(
        statement_id=record.statement_id,
        revision=latest.revision,
        source_kind=latest.source_kind,
        raw_text=latest.raw_text,
        manual_transcription_attested=latest.manual_transcription_attested,
        collector_id=latest.collector_id,
        topics=topics_from_json(latest.topics_json),
        created_at=latest.created_at,
        published_revision=published_revision,
    )


def _to_history_item(row: StatementRevisionRow) -> StatementRevisionHistoryItem:
    return StatementRevisionHistoryItem(
        revision=row.revision,
        source_kind=row.source_kind,
        raw_text=row.raw_text,
        manual_transcription_attested=row.manual_transcription_attested,
        collector_id=row.collector_id,
        topics=topics_from_json(row.topics_json),
        created_at=row.created_at,
        created_by=row.created_by_user.username if row.created_by_user else None,
    )


@router.get("/examples", response_model=list[StatementPublic])
def list_examples(session: Session = Depends(get_db)) -> list[StatementPublic]:
    """The only corpus data an anonymous visitor may ever see: approved-public revisions."""
    published = [r for r in list_statement_records(session) if r.published_revision is not None]
    return [
        StatementPublic(
            statement_id=r.statement_id,
            raw_text=r.published_revision.raw_text,  # type: ignore[union-attr]
            topics=topics_from_json(r.published_revision.topics_json),  # type: ignore[union-attr]
        )
        for r in published
    ]


@router.get("/corpus", response_model=list[StatementPrivate])
def list_corpus(
    session: Session = Depends(get_db), _user: User = Depends(require_user)
) -> list[StatementPrivate]:
    return [_to_private(r) for r in list_statement_records(session)]


@router.post("/corpus", response_model=StatementPrivate, status_code=status.HTTP_201_CREATED)
def create_corpus_statement(
    payload: StatementCreateRequest,
    session: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> StatementPrivate:
    try:
        create_statement(
            session,
            statement_id=payload.statement_id,
            source_kind=payload.source_kind,
            raw_text=payload.raw_text,
            manual_transcription_attested=payload.manual_transcription_attested,
            collector_id=payload.collector_id,
            topics=payload.topics,
            created_by_user_id=user.id,
        )
    except DuplicateStatementError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    record = get_statement_record(session, payload.statement_id)
    assert record is not None
    return _to_private(record)


@router.get("/corpus/{statement_id}", response_model=StatementPrivate)
def get_corpus_statement(
    statement_id: str, session: Session = Depends(get_db), _user: User = Depends(require_user)
) -> StatementPrivate:
    record = get_statement_record(session, statement_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Statement not found")
    return _to_private(record)


@router.get("/corpus/{statement_id}/history", response_model=list[StatementRevisionHistoryItem])
def get_corpus_history(
    statement_id: str, session: Session = Depends(get_db), _user: User = Depends(require_user)
) -> list[StatementRevisionHistoryItem]:
    record = get_statement_record(session, statement_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Statement not found")
    return [_to_history_item(r) for r in record.revisions]


@router.patch("/corpus/{statement_id}", response_model=StatementPrivate)
def update_corpus_statement(
    statement_id: str,
    payload: StatementUpdateRequest,
    session: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> StatementPrivate:
    try:
        add_statement_revision(
            session,
            statement_id=statement_id,
            expected_revision=payload.expected_revision,
            raw_text=payload.raw_text,
            source_kind=payload.source_kind,
            manual_transcription_attested=payload.manual_transcription_attested,
            collector_id=payload.collector_id,
            topics=payload.topics,
            created_by_user_id=user.id,
        )
    except StatementNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except RevisionConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    record = get_statement_record(session, statement_id)
    assert record is not None
    return _to_private(record)


@router.post("/corpus/{statement_id}/publish", response_model=StatementPrivate)
def publish_corpus_statement(
    statement_id: str,
    payload: PublishRequest,
    session: Session = Depends(get_db),
    _user: User = Depends(require_csrf),
) -> StatementPrivate:
    try:
        publish_revision(session, statement_id, payload.revision)
    except StatementNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    record = get_statement_record(session, statement_id)
    assert record is not None
    return _to_private(record)


@router.post("/corpus/{statement_id}/unpublish", response_model=StatementPrivate)
def unpublish_corpus_statement(
    statement_id: str, session: Session = Depends(get_db), _user: User = Depends(require_csrf)
) -> StatementPrivate:
    try:
        unpublish(session, statement_id)
    except StatementNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    record = get_statement_record(session, statement_id)
    assert record is not None
    return _to_private(record)
