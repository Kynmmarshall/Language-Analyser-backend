# -*- coding: utf-8 -*-
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import grammar_utils

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_stage(name):
    return json.load(open(os.path.join(DATA_DIR, "grammar.json")))[name]


def test_original_grammar_has_left_recursion_marker_in_note():
    # The original grammar is deliberately left-recursive (S -> S CONJ CLAUSE);
    # this test just pins that the stage we ship as "original" is the one on
    # record, so a future edit can't silently swap it for an already-fixed one.
    stage = load_stage("original")
    assert ["S", "CONJ", "CLAUSE"] in stage["productions"]["S"]


def test_final_grammar_is_ll1_with_no_conflicts():
    grammar = load_stage("after_left_factoring")
    analysis = grammar_utils.analyze_grammar(grammar)
    assert analysis["is_ll1"] is True
    assert analysis["conflicts"] == []


def test_first_sets_for_known_nonterminals():
    grammar = load_stage("after_left_factoring")
    analysis = grammar_utils.analyze_grammar(grammar)
    assert set(analysis["first"]["NP"]) == {"DET", "PRON", "NOUN"}
    assert set(analysis["first"]["PP"]) == {"PREP"}


def test_follow_set_of_start_symbol_is_end_marker():
    grammar = load_stage("after_left_factoring")
    analysis = grammar_utils.analyze_grammar(grammar)
    assert analysis["follow"]["S"] == ["$"]


def test_ll1_table_has_entry_for_every_first_set_terminal():
    grammar = load_stage("after_left_factoring")
    analysis = grammar_utils.analyze_grammar(grammar)
    for nt, firsts in analysis["first"].items():
        for terminal in firsts:
            if terminal == "EPS":
                continue
            assert terminal in analysis["table"][nt], f"missing table[{nt}][{terminal}]"


def test_tag_sentence_maps_known_words_to_terminals():
    tokens = [{"token": "Taxi", "category": "NOUN"}, {"token": "for", "category": "PREP"}]
    terminals, skipped = grammar_utils.tag_sentence(tokens)
    assert terminals == ["NOUN", "PREP"]
    assert skipped == []


def test_tag_sentence_skips_unmappable_tokens():
    tokens = [{"token": "oh", "category": "SLANG"}, {"token": ".", "category": "PUNCT"}]
    terminals, skipped = grammar_utils.tag_sentence(tokens)
    assert terminals == []
    assert len(skipped) == 2
