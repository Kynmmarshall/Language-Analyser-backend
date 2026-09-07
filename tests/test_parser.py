"""Hand-computed parser tests: accept, epsilon, unknown/wrong-order/trailing rejection,
resource limits, and refusal to run against an ambiguous (non-LL(1)) table.
"""

from __future__ import annotations

import pytest

from yaounde_analyzer.core.grammar import compute_nullable
from yaounde_analyzer.core.ll1 import build_ll1_table, compute_first, compute_follow
from yaounde_analyzer.core.models import (
    GrammarSpec,
    ParserAction,
    Production,
    RejectionReason,
    SourceSpan,
    Token,
)
from yaounde_analyzer.core.parser import ParserConfigurationError, parse_tokens


def grammar(
    start: str, terminals: tuple[str, ...], nonterminals: tuple[str, ...], rules: list[tuple]
) -> GrammarSpec:
    productions = tuple(
        Production(id=f"p{i}", lhs=lhs, rhs=rhs) for i, (lhs, rhs) in enumerate(rules)
    )
    return GrammarSpec(
        version="test", start_symbol=start, terminals=terminals, nonterminals=nonterminals,
        productions=productions,
    )


def build_table(g: GrammarSpec):
    nullable = compute_nullable(g)
    first = compute_first(g, nullable)
    follow = compute_follow(g, first, nullable)
    return build_ll1_table(g, first, follow, nullable)


def token(terminal: str, raw: str, start: int, end: int) -> Token:
    return Token(
        raw=raw, canonical=raw.lower(), terminal=terminal, part_of_speech=terminal,
        rule_id="test", span=SourceSpan(start=start, end=end),
    )


# S -> OPTIONAL NOUN ; OPTIONAL -> VERB | epsilon  (same fixture as test_ll1.py)
OPTIONAL_GRAMMAR = grammar("S", ("VERB", "NOUN"), ("S", "OPTIONAL"), [
    ("S", ("OPTIONAL", "NOUN")), ("OPTIONAL", ("VERB",)), ("OPTIONAL", ())])


def test_accept_with_the_optional_symbol_present() -> None:
    tokens = (token("VERB", "sleep", 0, 5), token("NOUN", "cat", 6, 9))
    result = parse_tokens(tokens, OPTIONAL_GRAMMAR, build_table(OPTIONAL_GRAMMAR))
    assert result.accepted
    assert result.matched_token_count == 2
    assert result.trace[-1].action == ParserAction.ACCEPT
    assert result.tree is not None
    assert result.tree.symbol == "S"
    optional_node, noun_node = result.tree.children
    assert optional_node.children[0].token_span == SourceSpan(start=0, end=5)
    assert noun_node.token_span == SourceSpan(start=6, end=9)


def test_accept_via_the_epsilon_alternative() -> None:
    tokens = (token("NOUN", "cat", 0, 3),)
    result = parse_tokens(tokens, OPTIONAL_GRAMMAR, build_table(OPTIONAL_GRAMMAR))
    assert result.accepted
    assert result.matched_token_count == 1
    assert result.tree is not None
    optional_node, noun_node = result.tree.children
    assert optional_node.children == ()  # epsilon derivation has no children
    assert noun_node.token_span == SourceSpan(start=0, end=3)


def test_reject_unknown_token_is_lexical_not_syntactic() -> None:
    tokens = (token("UNKNOWN", "marché", 3, 9),)
    result = parse_tokens(tokens, OPTIONAL_GRAMMAR, build_table(OPTIONAL_GRAMMAR))
    assert not result.accepted
    assert result.rejection_reason == RejectionReason.LEXICAL_UNKNOWN_TOKEN
    assert result.failing_position == 3


def test_reject_known_tokens_in_an_unsupported_order() -> None:
    # OPTIONAL consumes the first VERB; the grammar then requires NOUN, not another VERB.
    tokens = (token("VERB", "sleep", 0, 5), token("VERB", "run", 6, 9))
    result = parse_tokens(tokens, OPTIONAL_GRAMMAR, build_table(OPTIONAL_GRAMMAR))
    assert not result.accepted
    assert result.rejection_reason == RejectionReason.SYNTAX_NO_TABLE_ENTRY
    assert result.expected_terminals == ("NOUN",)
    assert result.failing_position == 6
    assert result.matched_token_count == 1


def test_reject_trailing_input_after_a_complete_derivation() -> None:
    tokens = (
        token("VERB", "sleep", 0, 5), token("NOUN", "cat", 6, 9), token("VERB", "run", 10, 13)
    )
    result = parse_tokens(tokens, OPTIONAL_GRAMMAR, build_table(OPTIONAL_GRAMMAR))
    assert not result.accepted
    assert result.rejection_reason == RejectionReason.SYNTAX_TRAILING_INPUT
    assert result.failing_position == 10
    assert result.matched_token_count == 2


def test_resource_limit_is_a_distinct_reason_from_a_syntax_rejection() -> None:
    tokens = (token("VERB", "sleep", 0, 5), token("NOUN", "cat", 6, 9))
    result = parse_tokens(tokens, OPTIONAL_GRAMMAR, build_table(OPTIONAL_GRAMMAR), max_steps=1)
    assert not result.accepted
    assert result.rejection_reason == RejectionReason.RESOURCE_LIMIT_EXCEEDED


def test_empty_input_accepts_when_the_start_symbol_is_nullable() -> None:
    g = grammar("S", (), ("S", "A"), [("S", ("A",)), ("A", ())])
    result = parse_tokens((), g, build_table(g))
    assert result.accepted
    assert result.matched_token_count == 0
    assert result.tree is not None
    assert result.tree.children[0].children == ()


def test_refuses_to_parse_against_an_ambiguous_table() -> None:
    g = grammar("A", ("VERB", "NOUN", "NUMBER"), ("A",), [
        ("A", ("VERB", "NOUN")), ("A", ("VERB", "NUMBER"))])
    with pytest.raises(ParserConfigurationError, match="conflicts"):
        parse_tokens((token("VERB", "go", 0, 2),), g, build_table(g))
