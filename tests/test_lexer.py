"""Lexer tests: hand-labeled tokens, multiword precedence, and full corpus coverage."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest
from pydantic import ValidationError

from yaounde_analyzer.core.lexer import UNKNOWN_TERMINAL, tokenize
from yaounde_analyzer.core.lexicon import EntrySource, LexicalEntry, LexiconSpec
from yaounde_analyzer.core.specs import load_demo_lexicon

DEMO_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.json"
LEXICON = load_demo_lexicon()


def test_hand_labeled_tokens_have_exact_raw_and_span() -> None:
    text = "On m'a djoss."
    tokens = tokenize(text, LEXICON)
    assert [(t.raw, t.canonical, t.terminal) for t in tokens] == [
        ("On", "on", "PRON"),
        ("m'a", "m'a", "VERB"),
        ("djoss", "djoss", "VERB"),
    ]
    # Raw text slices must equal exactly what the original span covers.
    for token in tokens:
        assert text[token.span.start : token.span.end] == token.raw
    # The trailing period is trivia and must not appear as a token.
    assert all(token.raw != "." for token in tokens)


def test_multiword_entry_wins_over_single_word_match() -> None:
    tokens = tokenize("sa caisse est à sec.", LEXICON)
    assert tokens[-1].raw == "à sec"
    assert tokens[-1].terminal == "ADJ"
    assert tokens[-1].is_multiword is True
    assert len(tokens[-1].component_spans) == 2
    assert tokens[-1].component_spans[0].start < tokens[-1].component_spans[1].start


def test_three_word_multiword_entry_and_standalone_first_word() -> None:
    tokens = tokenize("au lieu de waka dehors", LEXICON)
    assert tokens[0].canonical == "au lieu de"
    assert tokens[0].terminal == "PREP"
    assert len(tokens[0].component_spans) == 3
    # Elsewhere "au" alone (not followed by "lieu de") must still resolve on its own.
    standalone = tokenize("on go au kwatt", LEXICON)
    assert [t.canonical for t in standalone] == ["on", "go", "au", "kwatt"]


def test_multiword_match_is_blocked_across_punctuation() -> None:
    # "au, lieu de" has a comma between "au" and "lieu": the phrase must not match.
    tokens = tokenize("au, lieu de", LEXICON)
    assert [t.terminal for t in tokens] == ["PREP", UNKNOWN_TERMINAL, "PREP"]
    assert tokens[1].raw == "lieu"


def test_unknown_word_is_preserved_not_dropped() -> None:
    tokens = tokenize("On go au marché.", LEXICON)
    unknown = [t for t in tokens if t.terminal == UNKNOWN_TERMINAL]
    assert len(unknown) == 1
    assert unknown[0].raw == "marché"
    assert unknown[0].span.start == "On go au ".__len__()


def test_whitespace_and_punctuation_are_trivia() -> None:
    tokens = tokenize("On   go,  au   kwatt!!!", LEXICON)
    assert [t.canonical for t in tokens] == ["on", "go", "au", "kwatt"]


def test_offsets_use_code_points_not_utf16_units() -> None:
    # A non-BMP emoji before "combi" must not corrupt the offset of the following word.
    text = "\U0001f4f1 combi va."
    tokens = tokenize(text, LEXICON)
    combi = next(t for t in tokens if t.canonical == "combi")
    assert text[combi.span.start : combi.span.end] == "combi"
    assert combi.span.start == 2  # one emoji code point + one space


def test_decomposed_unicode_input_resolves_to_the_same_lexicon_entry() -> None:
    composed = "à sec"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed  # sanity check the two forms actually differ
    tokens = tokenize(f"est {decomposed}.", LEXICON)
    assert tokens[-1].canonical == "à sec"
    assert tokens[-1].terminal == "ADJ"
    # The raw slice preserves the original decomposed input untouched.
    assert tokens[-1].raw == decomposed


def test_full_demo_corpus_tokenizes_with_no_unknown_words() -> None:
    records = json.loads(DEMO_CORPUS_PATH.read_text(encoding="utf-8"))
    for record in records:
        tokens = tokenize(record["raw_text"], LEXICON)
        unknown = [t.raw for t in tokens if t.terminal == UNKNOWN_TERMINAL]
        assert unknown == [], f"{record['statement_id']} has unrecognized words: {unknown}"


def test_interjection_and_formula_entries_tokenize_as_single_units() -> None:
    assert [(t.canonical, t.terminal) for t in tokenize("Ashia !", LEXICON)] == [
        ("ashia", "INTJ")
    ]
    # The formula wins over the separate 'on' and 'dit' entries that also exist.
    assert [(t.canonical, t.terminal) for t in tokenize("On dit quoi ?", LEXICON)] == [
        ("on dit quoi", "FORMULA")
    ]


def test_words_outside_a_formula_still_resolve_on_their_own() -> None:
    # Adding 'on dit quoi' must not swallow 'on' or 'dit' in unrelated positions.
    assert [t.canonical for t in tokenize("il dit que on go", LEXICON)] == [
        "il", "dit", "que", "on", "go",
    ]


def test_corpus_sourced_entries_must_cite_evidence() -> None:
    corpus_entries = [e for e in LEXICON.entries if e.source is EntrySource.CORPUS]
    assert corpus_entries, "expected the lexicon to retain corpus-attested entries"
    for entry in corpus_entries:
        assert entry.evidence_statement_ids, entry.rule_id


def test_dictionary_sourced_entries_are_marked_and_uncited() -> None:
    dictionary_entries = [e for e in LEXICON.entries if e.source is EntrySource.DICTIONARY]
    assert dictionary_entries, "expected dictionary-derived entries to be present"
    for entry in dictionary_entries:
        assert entry.evidence_statement_ids == (), entry.rule_id


def test_a_corpus_entry_without_evidence_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cites no statement"):
        LexiconSpec(
            version="test",
            entries=(
                LexicalEntry(
                    canonical="combi",
                    terminal="NOUN",
                    part_of_speech="noun",
                    rule_id="test.lex.combi",
                ),
            ),
        )


def test_tokenizer_always_advances_on_pathological_input() -> None:
    # A run of unsupported symbols must not hang the lexer or lose input.
    text = "\u2603\u2603\u2603"
    tokens = tokenize(text, LEXICON)
    assert len(tokens) == 3
    assert all(t.terminal == UNKNOWN_TERMINAL for t in tokens)
