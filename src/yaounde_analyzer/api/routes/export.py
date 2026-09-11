"""Reproducible evidence export: grammar/lexicon snapshot + corpus + analysis results.

Requires authentication for both scopes: even the "published" scope assembles a bulk
research artifact (full grammar/lexicon plus per-statement analysis), which is a
collector/reviewer action, not the anonymous public projection served by /api/examples.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from io import StringIO
from typing import cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from yaounde_analyzer import __version__
from yaounde_analyzer.api.deps import get_analyzer, get_db, require_user
from yaounde_analyzer.api.repository import list_statement_records, topics_from_json
from yaounde_analyzer.api.schemas import EvidenceBundle, ExportStatement
from yaounde_analyzer.core.analysis import AnalysisResult, PreparedAnalyzer, analyze_statement
from yaounde_analyzer.core.corpus import StatementRevision
from yaounde_analyzer.core.models import SourceKind
from yaounde_analyzer.storage.models import StatementRecord, StatementRevisionRow, User

router = APIRouter(prefix="/api", tags=["export"])

ExportRow = tuple[StatementRecord, StatementRevisionRow, bool]


def _spec_hash(analyzer: PreparedAnalyzer) -> str:
    """A short, content-derived fingerprint of the exact lexicon/grammar in use."""
    payload = analyzer.lexicon.model_dump_json() + analyzer.descriptive_grammar.model_dump_json()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _select_export_rows(records: Sequence[StatementRecord], scope: str) -> list[ExportRow]:
    selected: list[ExportRow] = []
    for record in records:
        if scope == "published":
            if record.published_revision is None:
                continue
            selected.append((record, record.published_revision, True))
        else:
            latest = record.revisions[-1]
            is_published = (
                record.published_revision is not None and record.published_revision_id == latest.id
            )
            selected.append((record, latest, is_published))
    return selected


def _to_core_revision(record: StatementRecord, row: StatementRevisionRow) -> StatementRevision:
    return StatementRevision(
        statement_id=record.statement_id,
        revision=row.revision,
        source_kind=cast(SourceKind, row.source_kind),
        raw_text=row.raw_text,
        manual_transcription_attested=row.manual_transcription_attested,
        collector_id=row.collector_id,
        topics=topics_from_json(row.topics_json),
        created_at=row.created_at,
    )


def _build_bundle(
    session: Session, analyzer: PreparedAnalyzer, scope: str
) -> tuple[tuple[ExportStatement, ...], tuple[AnalysisResult, ...]]:
    rows = _select_export_rows(list_statement_records(session), scope)
    statements: list[ExportStatement] = []
    results: list[AnalysisResult] = []
    for record, row, is_published in rows:
        revision = _to_core_revision(record, row)
        result = analyze_statement(revision, analyzer)
        results.append(result)
        redacted = scope == "published"
        statements.append(
            ExportStatement(
                statement_id=record.statement_id,
                revision=row.revision,
                source_kind=row.source_kind,
                raw_text=row.raw_text,
                topics=topics_from_json(row.topics_json),
                collector_id=None if redacted else row.collector_id,
                manual_transcription_attested=(
                    None if redacted else row.manual_transcription_attested
                ),
                published=is_published,
                created_at=row.created_at,
            )
        )
    return tuple(statements), tuple(results)


@router.get("/export", response_model=EvidenceBundle)
def get_evidence_export(
    scope: str = Query("all", pattern="^(all|published)$"),
    session: Session = Depends(get_db),
    analyzer: PreparedAnalyzer = Depends(get_analyzer),
    _user: User = Depends(require_user),
) -> EvidenceBundle:
    statements, results = _build_bundle(session, analyzer, scope)
    return EvidenceBundle(
        generated_at=datetime.now(UTC),
        scope=scope,
        analyzer_version=__version__,
        spec_hash=_spec_hash(analyzer),
        lexicon=analyzer.lexicon.entries,
        descriptive_grammar=analyzer.descriptive_grammar,
        grammar=analyzer.grammar,
        statements=statements,
        results=results,
    )


@router.get("/export/csv")
def get_evidence_export_csv(
    scope: str = Query("all", pattern="^(all|published)$"),
    session: Session = Depends(get_db),
    analyzer: PreparedAnalyzer = Depends(get_analyzer),
    _user: User = Depends(require_user),
) -> Response:
    statements, results = _build_bundle(session, analyzer, scope)
    results_by_id = {result.statement_revision_id: result for result in results}

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "statement_id", "revision", "source_kind", "published", "collector_id",
        "manual_transcription_attested", "topics", "raw_text",
        "accepted", "rejection_reason", "token_count", "matched_topics",
    ])
    for statement in statements:
        result = results_by_id[f"{statement.statement_id}@{statement.revision}"]
        writer.writerow([
            statement.statement_id, statement.revision, statement.source_kind,
            statement.published, statement.collector_id or "",
            "" if statement.manual_transcription_attested is None
            else statement.manual_transcription_attested,
            ";".join(statement.topics), statement.raw_text,
            result.parse.accepted, result.parse.rejection_reason or "", len(result.tokens),
            ";".join(topic.topic for topic in result.topics),
        ])

    filename = f"francanglais-evidence-{scope}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
