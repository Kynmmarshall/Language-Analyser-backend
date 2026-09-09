"""Protected corpus statistics: frequency, acceptance, topic, and borrowing-origin evidence.

Requires authentication because it aggregates over every record's latest revision,
including unpublished drafts, not just the approved-public projection.
"""

from __future__ import annotations

from collections import Counter
from typing import cast

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from yaounde_analyzer.api.deps import get_analyzer, get_db, require_user
from yaounde_analyzer.api.repository import list_statement_records, topics_from_json
from yaounde_analyzer.api.schemas import FrequencyItem, StatisticsView
from yaounde_analyzer.core.analysis import PreparedAnalyzer, analyze_corpus, compute_statistics
from yaounde_analyzer.core.corpus import StatementRevision
from yaounde_analyzer.core.models import SourceKind
from yaounde_analyzer.storage.models import StatementRecord, User

router = APIRouter(prefix="/api", tags=["statistics"])


def _to_core_revision(record: StatementRecord) -> StatementRevision:
    latest = record.revisions[-1]
    return StatementRevision(
        statement_id=record.statement_id,
        revision=latest.revision,
        source_kind=cast(SourceKind, latest.source_kind),
        raw_text=latest.raw_text,
        manual_transcription_attested=latest.manual_transcription_attested,
        collector_id=latest.collector_id,
        topics=topics_from_json(latest.topics_json),
        created_at=latest.created_at,
    )


def _sorted_counts(counter: Counter[str]) -> tuple[FrequencyItem, ...]:
    return tuple(
        FrequencyItem(term=term, count=count)
        for term, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    )


@router.get("/statistics", response_model=StatisticsView)
def get_statistics(
    session: Session = Depends(get_db),
    analyzer: PreparedAnalyzer = Depends(get_analyzer),
    _user: User = Depends(require_user),
) -> StatisticsView:
    revisions: list[StatementRevision] = []
    skipped = 0
    for record in list_statement_records(session):
        try:
            revisions.append(_to_core_revision(record))
        except ValidationError:
            # A stored row that fails the stricter core contract (should not happen if the
            # corpus API is the only writer) is reported, not allowed to crash the screen.
            skipped += 1

    results = analyze_corpus(tuple(revisions), analyzer)
    stats = compute_statistics(results)

    topic_counts: Counter[str] = Counter()
    origin_counts: Counter[str] = Counter()
    for result in results:
        for topic in result.topics:
            topic_counts[topic.topic] += 1
        for token in result.tokens:
            for origin in token.language_candidates:
                origin_counts[str(origin)] += 1

    return StatisticsView(
        statement_count=stats.statement_count,
        accepted_count=stats.accepted_count,
        rejected_count=stats.rejected_count,
        skipped_invalid_count=skipped,
        raw_frequency=_sorted_counts(Counter(stats.raw_frequency)),
        canonical_frequency=_sorted_counts(Counter(stats.canonical_frequency)),
        terminal_frequency=_sorted_counts(Counter(stats.terminal_frequency)),
        unknown_words=stats.unknown_words,
        topic_counts=_sorted_counts(topic_counts),
        language_candidate_counts=_sorted_counts(origin_counts),
    )
