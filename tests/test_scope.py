import pytest
from pydantic import ValidationError

from yaounde_analyzer.core.corpus import AnalysisSnapshot, StatementRevision
from yaounde_analyzer.core.models import (
    AnalysisRequest,
    AnalysisResult,
    GrammarSpec,
    LanguageLabel,
    SourceSpan,
    Token,
)
from yaounde_analyzer.core.scope import MAX_INPUT_CHARACTERS, TARGET_VARIETY, FrancanglaisModel


@pytest.mark.parametrize(
    "contract", [AnalysisRequest, AnalysisResult, GrammarSpec, StatementRevision, AnalysisSnapshot]
)
def test_contracts_inherit_one_fixed_analysis_target(contract: type[FrancanglaisModel]) -> None:
    schema = contract.model_json_schema()
    assert schema["properties"]["target_variety"]["const"] == TARGET_VARIETY
    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError, match="target_variety"):
        contract.model_validate({"target_variety": "english"})


def test_request_preserves_original_unicode_and_spacing() -> None:
    text = "  Le re\u0301seau au kwatt ! \U0001f4f1\n"
    request = AnalysisRequest(text=text)
    restored = AnalysisRequest.model_validate_json(request.model_dump_json())
    assert restored.text == text
    assert restored.target_variety == TARGET_VARIETY


@pytest.mark.parametrize("text", ["", " ", "\n\t", "a" * (MAX_INPUT_CHARACTERS + 1)])
def test_request_rejects_blank_or_oversized_input(text: str) -> None:
    with pytest.raises(ValidationError):
        AnalysisRequest(text=text)


def test_request_limit_counts_code_points_not_utf16_units() -> None:
    text = "\U0001f4f1" * MAX_INPUT_CHARACTERS
    assert AnalysisRequest(text=text).text == text


def test_request_cannot_enable_another_language_mode() -> None:
    with pytest.raises(ValidationError, match="language"):
        AnalysisRequest.model_validate({"text": "Combi, on go.", "language": "french"})


def test_single_target_does_not_remove_borrowing_origin_annotations() -> None:
    token = Token(
        raw="go",
        canonical="go",
        terminal="VERB",
        part_of_speech="VERB",
        language_candidates=(LanguageLabel.ENGLISH, LanguageLabel.PIDGIN),
        rule_id="demo-go",
        span=SourceSpan(start=0, end=2),
    )
    assert token.language_candidates == (LanguageLabel.ENGLISH, LanguageLabel.PIDGIN)


def test_target_cannot_be_changed_after_validation() -> None:
    request = AnalysisRequest(text="Combi, on go.")
    with pytest.raises(ValidationError, match="frozen"):
        request.target_variety = TARGET_VARIETY