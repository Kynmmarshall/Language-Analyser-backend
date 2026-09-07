"""Integration tests wiring the lexer, demo grammar/lexicon, parser, and topic/frequency
analysis together.

The demo grammar intentionally covers only a small NP/VP/PP clause shape derived from
real corpus vocabulary. None of the 12 full demo.json statements are expected to be fully
accepted end to end (they contain far more structure than this small grammar covers) — the
short sentences below are separately constructed teaching examples, built from the same
real vocabulary, used to demonstrate that the pipeline genuinely accepts and rejects
correctly rather than always rejecting.
"""

from __future__ import annotations

import json
from pathlib import Path

from yaounde_analyzer.core.analysis import (
    PreparedAnalyzer,
    analyze_corpus,
    analyze_tokens_and_parse,
    compute_statistics,
    match_topics,
)
from yaounde_analyzer.core.corpus import validate_import
from yaounde_analyzer.core.lexer import tokenize
from yaounde_analyzer.core.models import RejectionReason
from yaounde_analyzer.core.specs import load_demo_grammar, load_demo_lexicon

DEMO_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.json"
LEXICON = load_demo_lexicon()
GRAMMAR = load_demo_grammar()
ANALYZER = PreparedAnalyzer(LEXICON, GRAMMAR)


def test_the_demo_grammar_is_genuinely_conflict_free_ll1() -> None:
    ANALYZER.check()  # must not raise
    assert ANALYZER.table.is_ll1
    # VP's three VERB-first alternatives genuinely need left-factoring to become LL(1);
    # this is not a no-op, so the transformation ledger must record real steps.
    assert len(ANALYZER.transformation_steps) > 0
    assert ANALYZER.grammar != ANALYZER.descriptive_grammar


def test_a_verb_prepositional_phrase_sentence_is_accepted() -> None:
    tokens, parse, _ = analyze_tokens_and_parse("Combi va au kwatt.", ANALYZER)
    assert parse.accepted
    assert parse.matched_token_count == len(tokens)


def test_a_pronoun_subject_sentence_is_accepted() -> None:
    _, parse, _ = analyze_tokens_and_parse("On go au school.", ANALYZER)
    assert parse.accepted


def test_a_bare_verb_sentence_is_accepted() -> None:
    _, parse, _ = analyze_tokens_and_parse("Le taximan waka.", ANALYZER)
    assert parse.accepted


def test_verb_first_order_is_rejected_as_unsupported_syntax() -> None:
    _, parse, _ = analyze_tokens_and_parse("Va combi.", ANALYZER)
    assert not parse.accepted
    assert parse.rejection_reason == RejectionReason.SYNTAX_NO_TABLE_ENTRY


def test_unknown_vocabulary_is_rejected_as_lexical_not_syntactic() -> None:
    _, parse, _ = analyze_tokens_and_parse("On go au marché.", ANALYZER)
    assert not parse.accepted
    assert parse.rejection_reason == RejectionReason.LEXICAL_UNKNOWN_TOKEN


def test_topic_match_shows_its_exact_evidence() -> None:
    tokens = tokenize("Ils ont encore coupé le courant.", LEXICON)
    topics = match_topics(tokens)
    assert len(topics) == 1
    assert topics[0].topic == "electricity"
    assert set(topics[0].matched_terms) == {"coupé", "courant"}


def test_full_demo_corpus_analyzes_without_errors_and_recalls_hand_labels() -> None:
    records = json.loads(DEMO_CORPUS_PATH.read_text(encoding="utf-8"))
    revisions = validate_import(records)
    results = analyze_corpus(revisions, ANALYZER)
    assert len(results) == len(records)

    detected_by_statement = {
        result.statement_revision_id.split("@")[0]: {m.topic for m in result.topics}
        for result in results
    }
    for record in records:
        hand_labels = set(record["topics"])
        detected = detected_by_statement[record["statement_id"]]
        # The keyword matcher is allowed to find extra, transparently-evidenced topics,
        # but must never miss a topic a human reviewer already confirmed.
        assert hand_labels <= detected, (record["statement_id"], hand_labels, detected)

    # This small demo grammar is not expected to fully accept any real, full statement —
    # only the short constructed sentences above exercise a successful ACCEPT.
    assert all(not result.parse.accepted for result in results)


def test_corpus_statistics_reports_full_lexical_coverage() -> None:
    records = json.loads(DEMO_CORPUS_PATH.read_text(encoding="utf-8"))
    revisions = validate_import(records)
    results = analyze_corpus(revisions, ANALYZER)
    stats = compute_statistics(results)

    assert stats.statement_count == 12
    assert stats.unknown_words == ()
    assert stats.rejected_count == 12
    assert stats.canonical_frequency["kwatt"] == 4  # demo-001, 003, 008, 009
    assert stats.raw_frequency["Combi"] == 3  # capitalized in demo-001, 002, 007
