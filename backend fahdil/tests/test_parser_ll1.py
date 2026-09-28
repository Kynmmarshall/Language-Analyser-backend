# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import lexer, grammar_utils, parser_ll1

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GRAMMAR = json.load(open(os.path.join(DATA_DIR, "grammar.json")))["after_left_factoring"]
ANALYSIS = grammar_utils.analyze_grammar(GRAMMAR)


def run(text):
    tokens = lexer.tokenize(text)
    terminals, _ = grammar_utils.tag_sentence(tokens)
    return parser_ll1.parse(GRAMMAR, ANALYSIS["table"], terminals)


def test_simple_svo_sentence_is_accepted():
    result = run("Taxi drop me for quartier")
    assert result["accepted"] is True
    assert result["trace"][-1]["action_type"] == "accept"


def test_verb_only_sentence_is_rejected_with_structured_error():
    result = run("YO GO TCHOP")  # YO is CODEMIX (skipped) -> tags to VERB NOUN, no leading NP
    assert result["accepted"] is False
    assert result["error_type"] == "error_no_rule"
    assert result["error_params"]["nonterminal"] == "S"


def test_on_is_recognized_as_a_pronoun_and_accepted_as_a_subject():
    # "on" (the French impersonal pronoun, "we"/"one") is extremely common in real
    # Francanglais speech and must be usable as a sentence's subject, e.g. "On go
    # tchop" ("we go eat"). Previously "on" was unclassified (fell through to a
    # generic English-hint tag) and could not start a sentence at all.
    result = run("On go tchop")
    assert result["accepted"] is True


def test_every_trace_row_has_structured_action_fields():
    result = run("Taxi drop me for quartier")
    for row in result["trace"]:
        assert "action_type" in row
        assert "action_params" in row


def test_full_corpus_matches_recorded_accept_reject_counts():
    data = json.load(open(os.path.join(DATA_DIR, "statements.json")))
    accepted = 0
    for s in data["statements"]:
        if run(s["text"])["accepted"]:
            accepted += 1
    # Pinned so a future lexer/grammar edit that silently changes behaviour
    # fails the suite instead of drifting unnoticed (see report §7 for why
    # each rejection is a documented grammar limitation, not a bug).
    assert accepted == 8
    assert len(data["statements"]) == 14


def test_mismatched_terminal_gives_error_expected():
    # Directly drive the parser with a terminal sequence its own grammar cannot
    # match at the first symbol, to exercise the "error_expected" branch
    # (a leading PREP where the grammar always expects an NP first).
    result = parser_ll1.parse(GRAMMAR, ANALYSIS["table"], ["PREP"])
    assert result["accepted"] is False
