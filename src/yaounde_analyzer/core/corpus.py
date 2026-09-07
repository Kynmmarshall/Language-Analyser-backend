"""Provenance declarations require human review; validation cannot prove authenticity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field, model_validator

from yaounde_analyzer.core.models import AnalysisResult, SourceKind
from yaounde_analyzer.core.scope import FrancanglaisModel


class CorpusImportError(ValueError):
    """Raised when a batch of statement records fails corpus import validation."""


class StatementRevision(FrancanglaisModel):
    """One immutable, append-only revision of a collected statement."""

    statement_id: str
    revision: int = Field(ge=1)
    source_kind: SourceKind
    raw_text: str = Field(min_length=1)
    manual_transcription_attested: bool
    collector_id: str
    topics: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _check_field_provenance(self) -> StatementRevision:
        if self.source_kind == "field" and not self.manual_transcription_attested:
            raise ValueError(
                f"statement {self.statement_id!r} revision {self.revision} is marked as field "
                "data but lacks manual-transcription attestation"
            )
        return self


class AnalysisSnapshot(FrancanglaisModel):
    """A frozen, reproducible bundle of analysis results tied to exact input versions."""

    snapshot_id: str
    analyzer_version: str
    spec_hash: str
    statement_revision_ids: tuple[str, ...]
    results: tuple[AnalysisResult, ...]
    created_at: datetime

    @model_validator(mode="after")
    def _check_result_coverage(self) -> AnalysisSnapshot:
        result_ids = {r.statement_revision_id for r in self.results}
        missing = set(self.statement_revision_ids) - result_ids
        if missing:
            raise ValueError(f"snapshot is missing results for statement revisions {missing}")
        return self

    def is_field_only(self, revisions_by_id: dict[str, StatementRevision]) -> bool:
        """True if every referenced revision is authentic field data, not a demo fixture."""
        return all(
            revisions_by_id[rid].source_kind == "field" for rid in self.statement_revision_ids
        )


def validate_import(records: list[dict[str, Any]]) -> list[StatementRevision]:
    """Validate and parse a batch of raw corpus records, rejecting the whole batch on any error.

    Each record must resolve to a well-formed StatementRevision; field-sourced records
    without manual-transcription attestation are rejected here rather than silently
    imported as unverified data.
    """
    if not records:
        raise CorpusImportError("import batch is empty")

    revisions: list[StatementRevision] = []
    seen: set[tuple[str, int]] = set()
    errors: list[str] = []

    for index, record in enumerate(records):
        try:
            revision = StatementRevision(**record)
        except Exception as exc:  # noqa: BLE001 - collect all row errors before failing
            errors.append(f"record {index}: {exc}")
            continue
        key = (revision.statement_id, revision.revision)
        if key in seen:
            errors.append(f"record {index}: duplicate statement_id/revision {key}")
            continue
        seen.add(key)
        revisions.append(revision)

    if errors:
        raise CorpusImportError("; ".join(errors))

    return revisions


def utc_now() -> datetime:
    return datetime.now(UTC)
