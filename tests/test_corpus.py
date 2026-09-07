"""Tests for corpus statement contracts and import validation."""

from __future__ import annotations

import pytest

from yaounde_analyzer.core.corpus import (
    CorpusImportError,
    StatementRevision,
    validate_import,
)


def base_record(**overrides: object) -> dict:
    record = {
        "statement_id": "stmt-001",
        "revision": 1,
        "source_kind": "demo",
        "raw_text": "Chauffeur, drop me for junction!",
        "manual_transcription_attested": False,
        "collector_id": "demo-fixture",
        "created_at": "2026-09-01T00:00:00Z",
    }
    record.update(overrides)
    return record


def test_field_statement_requires_manual_transcription_attestation() -> None:
    with pytest.raises(ValueError, match="manual-transcription attestation"):
        StatementRevision(**base_record(source_kind="field", manual_transcription_attested=False))


def test_field_statement_with_attestation_is_valid() -> None:
    revision = StatementRevision(
        **base_record(source_kind="field", manual_transcription_attested=True)
    )
    assert revision.source_kind == "field"


def test_demo_statement_does_not_require_attestation() -> None:
    revision = StatementRevision(**base_record(source_kind="demo"))
    assert revision.manual_transcription_attested is False


def test_validate_import_rejects_empty_batch() -> None:
    with pytest.raises(CorpusImportError, match="empty"):
        validate_import([])


def test_validate_import_rejects_duplicate_statement_revision() -> None:
    record = base_record()
    with pytest.raises(CorpusImportError, match="duplicate"):
        validate_import([record, dict(record)])


def test_validate_import_rejects_unattested_field_record_without_importing_any() -> None:
    good = base_record(statement_id="stmt-002")
    bad = base_record(
        statement_id="stmt-003", source_kind="field", manual_transcription_attested=False
    )
    with pytest.raises(CorpusImportError, match="manual-transcription attestation"):
        validate_import([good, bad])


def test_validate_import_returns_parsed_revisions() -> None:
    records = [base_record(), base_record(statement_id="stmt-002")]
    revisions = validate_import(records)
    assert [r.statement_id for r in revisions] == ["stmt-001", "stmt-002"]
