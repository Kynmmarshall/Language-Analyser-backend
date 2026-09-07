"""Smoke and validation tests for the storage-independent core contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from yaounde_analyzer.core.models import (
    EOF,
    GrammarSpec,
    LanguageLabel,
    ParserAction,
    ParseResult,
    Production,
    RejectionReason,
    SourceSpan,
    Token,
    TraceStep,
)


def make_token(raw: str, terminal: str, start: int, end: int) -> Token:
    return Token(
        raw=raw,
        canonical=raw.lower(),
        terminal=terminal,
        part_of_speech=terminal,
        rule_id="test-rule",
        span=SourceSpan(start=start, end=end),
    )


def test_source_span_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(start=5, end=2)


def test_token_defaults_to_uncertain_language() -> None:
    token = make_token("hala", "VERB", 0, 4)
    assert token.language_candidates == (LanguageLabel.UNCERTAIN,)
    assert token.is_multiword is False


def test_multiword_token_requires_component_spans() -> None:
    with pytest.raises(ValidationError):
        Token(
            raw="dey for front",
            canonical="dey for front",
            terminal="VERB",
            part_of_speech="VERB",
            rule_id="mwe-rule",
            span=SourceSpan(start=0, end=13),
            is_multiword=True,
        )


def test_grammar_spec_rejects_overlapping_symbols() -> None:
    with pytest.raises(ValidationError):
        GrammarSpec(
            version="test",
            start_symbol="S",
            terminals=("NOUN",),
            nonterminals=("S", "NOUN"),
            productions=(Production(id="p1", lhs="S", rhs=("NOUN",)),),
        )


def test_grammar_spec_rejects_undeclared_symbol_in_rhs() -> None:
    with pytest.raises(ValidationError):
        GrammarSpec(
            version="test",
            start_symbol="S",
            terminals=("NOUN",),
            nonterminals=("S",),
            productions=(Production(id="p1", lhs="S", rhs=("VERB",)),),
        )


def test_grammar_spec_accepts_epsilon_production() -> None:
    grammar = GrammarSpec(
        version="test",
        start_symbol="S",
        terminals=("NOUN",),
        nonterminals=("S",),
        productions=(
            Production(id="p1", lhs="S", rhs=("NOUN",)),
            Production(id="p2", lhs="S", rhs=()),
        ),
    )
    assert grammar.productions[1].rhs == ()


def test_parse_result_accepted_must_not_carry_rejection_reason() -> None:
    with pytest.raises(ValidationError):
        ParseResult(accepted=True, rejection_reason=RejectionReason.LEXICAL_UNKNOWN_TOKEN)


def test_parse_result_rejected_requires_reason() -> None:
    with pytest.raises(ValidationError):
        ParseResult(accepted=False)


def test_parse_result_accepts_valid_trace() -> None:
    result = ParseResult(
        accepted=True,
        matched_token_count=2,
        applied_production_ids=("p1",),
        trace=(
            TraceStep(
                step=0,
                stack=("S", EOF),
                remaining_terminals=("NOUN", EOF),
                action=ParserAction.EXPAND,
                production_id="p1",
            ),
            TraceStep(
                step=1,
                stack=("NOUN", EOF),
                remaining_terminals=("NOUN", EOF),
                action=ParserAction.MATCH,
            ),
        ),
    )
    assert result.accepted
    assert result.rejection_reason is None
