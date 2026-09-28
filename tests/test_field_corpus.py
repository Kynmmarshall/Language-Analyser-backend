"""Confirms the bundled field corpus is wired to the same validation as any import."""

from __future__ import annotations

from yaounde_analyzer.core.corpus import validate_import
from yaounde_analyzer.core.specs import load_demo_corpus_records

# Collector ids are the team's student numbers; every statement must be attributable.
COLLECTORS = {"ICTU20241386", "ICTU20241297", "ICTU20241393"}


def load_records() -> list[dict]:
    return load_demo_corpus_records()


def test_corpus_meets_the_minimum_statement_count() -> None:
    assert len(load_records()) >= 10


def test_corpus_imports_cleanly_and_is_labelled_field() -> None:
    revisions = validate_import(load_records())
    assert len(revisions) == len(load_records())
    assert all(r.source_kind == "field" for r in revisions)


def test_corpus_preserves_raw_text_exactly() -> None:
    records = load_records()
    revisions = validate_import(records)
    by_id = {r.statement_id: r for r in revisions}
    for record in records:
        assert by_id[record["statement_id"]].raw_text == record["raw_text"]


def test_every_statement_is_manually_transcribed_and_attributed() -> None:
    revisions = validate_import(load_records())
    assert all(r.manual_transcription_attested for r in revisions)
    assert {r.collector_id for r in revisions} == COLLECTORS


def test_collection_is_shared_across_the_whole_team() -> None:
    revisions = validate_import(load_records())
    for collector in COLLECTORS:
        assert sum(r.collector_id == collector for r in revisions) >= 3


def test_statement_ids_are_unique() -> None:
    revisions = validate_import(load_records())
    assert len({r.statement_id for r in revisions}) == len(revisions)


def test_corpus_explicitly_targets_francanglais() -> None:
    records = load_records()
    assert all(record["target_variety"] == "cameroon_francanglais" for record in records)
    revisions = validate_import(records)
    assert all(revision.target_variety == "cameroon_francanglais" for revision in revisions)
