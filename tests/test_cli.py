import json

import pytest

from yaounde_analyzer.cli import main


def test_cli_exposes_fixed_scope(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--scope"]) == 0
    assert capsys.readouterr().out.strip() == "cameroon_francanglais"


def test_cli_does_not_offer_a_language_switch() -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--language", "english"])
    assert raised.value.code == 2


def test_cli_prints_help_with_no_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_cli_analyze_accepts_a_constructed_sentence(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", "Combi va au kwatt."]) == 0
    out = capsys.readouterr().out
    assert "ACCEPTED" in out
    assert "kwatt" in out


def test_cli_analyze_json_output_is_well_formed(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", "On go au marché.", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["parse"]["accepted"] is False
    assert payload["parse"]["rejection_reason"] == "lexical_unknown_token"
    assert any(token["terminal"] == "UNKNOWN" for token in payload["tokens"])


def test_cli_grammar_check_reports_ll1_and_steps(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["grammar-check", "--show-steps"]) == 0
    out = capsys.readouterr().out
    assert "valid LL(1)" in out
    assert "Transformation steps" in out


def test_cli_corpus_validate_reports_count(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus_file = tmp_path / "corpus.json"
    corpus_file.write_text(
        json.dumps([
            {
                "statement_id": "t-001", "revision": 1, "source_kind": "demo",
                "raw_text": "Combi va au kwatt.", "manual_transcription_attested": False,
                "collector_id": "test", "created_at": "2026-09-01T00:00:00Z",
            }
        ]),
        encoding="utf-8",
    )
    assert main(["corpus-validate", str(corpus_file), "--analyze"]) == 0
    out = capsys.readouterr().out
    assert "Validated 1 statement revision(s)." in out
    assert "Accepted: 1  Rejected: 0" in out


def test_cli_corpus_validate_reports_failure(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus_file = tmp_path / "bad.json"
    corpus_file.write_text("[]", encoding="utf-8")
    assert main(["corpus-validate", str(corpus_file)]) == 1