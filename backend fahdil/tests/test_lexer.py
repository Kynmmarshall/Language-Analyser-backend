# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import lexer


def cats(text):
    return [t["category"] for t in lexer.tokenize(text)]


def toks(text):
    return [t["token"] for t in lexer.tokenize(text)]


def test_simple_sentence_categories():
    assert cats("Taxi drop me for quartier") == ["NOUN", "VERB", "PRON", "PREP", "NOUN"]


def test_multiword_phrase_survives_as_one_token():
    # Regression test for the placeholder bug: a digit-bearing placeholder
    # ("PHRASE1X") used to be re-split by the tokenizer's own NUMBER/WORD
    # regex into three separate tokens. The fix encodes the placeholder in
    # letters only; this must never regress.
    result = toks("Bendskin hala me small money for quartier")
    assert "small money" in result
    assert "PHRASE" not in " ".join(result)


def test_multiword_phrase_case_insensitive():
    # The lexer preserves the original casing of the matched surface text
    # (by design, for display purposes) while still matching case-insensitively.
    result = toks("SMALL MONEY for quartier")
    assert any(t.lower() == "small money" for t in result)


def test_unknown_word_is_tagged_codemix_not_dropped():
    tokens = lexer.tokenize("blahblah quartier")
    assert len(tokens) == 2
    assert tokens[0]["category"] == "CODEMIX"


def test_aux_word_not_classified_as_verb():
    # "dey" and "don" are aspect markers, not full verbs (see translation.py notes)
    tokens = lexer.tokenize("Essence no dey for station")
    by_word = {t["token"].lower(): t["category"] for t in tokens}
    assert by_word["dey"] == "AUX"


def test_on_is_classified_as_pronoun():
    # "on" (French impersonal pronoun, "we"/"one") is common in real Francanglais
    # speech and must not fall through to a generic English/CODEMIX classification.
    tokens = lexer.tokenize("On go tchop")
    by_word = {t["token"].lower(): t["category"] for t in tokens}
    assert by_word["on"] == "PRON"


def test_punctuation_and_numbers_classified_separately():
    tokens = lexer.tokenize("Le prix, 500 francs.")
    cats_seen = {t["category"] for t in tokens}
    assert "PUNCT" in cats_seen
    assert "NUMBER" in cats_seen


def test_empty_input_returns_no_tokens():
    assert lexer.tokenize("") == []


def test_all_corpus_phrases_survive_tokenization():
    import json
    data = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "statements.json")))
    for phrase in lexer.PHRASES:
        # every declared phrase must tokenize as a single token when isolated
        result = toks(phrase)
        assert phrase.lower() in [t.lower() for t in result], f"phrase {phrase!r} was fragmented: {result}"
