"""Confirms the demo corpus fixture is wired to the same validation as real imports."""

from __future__ import annotations

import json
from pathlib import Path

from yaounde_analyzer.core.corpus import validate_import

DEMO_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.json"


def load_demo_records() -> list[dict]:
    return json.loads(DEMO_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_demo_fixture_has_expected_statement_count() -> None:
    records = load_demo_records()
    assert 10 <= len(records) <= 15


def test_demo_fixture_imports_cleanly_and_is_labelled_demo() -> None:
    revisions = validate_import(load_demo_records())
    assert len(revisions) == len(load_demo_records())
    assert all(r.source_kind == "demo" for r in revisions)


def test_demo_fixture_preserves_raw_text_exactly() -> None:
    records = load_demo_records()
    revisions = validate_import(records)
    by_id = {r.statement_id: r for r in revisions}
    for record in records:
        assert by_id[record["statement_id"]].raw_text == record["raw_text"]


def test_demo_fixture_cannot_satisfy_field_data_requirement() -> None:
    revisions = validate_import(load_demo_records())
    assert not any(r.manual_transcription_attested for r in revisions)


def test_demo_fixture_explicitly_targets_francanglais() -> None:
    records = load_demo_records()
    assert all(record["target_variety"] == "cameroon_francanglais" for record in records)
    revisions = validate_import(records)
    assert all(revision.target_variety == "cameroon_francanglais" for revision in revisions)
