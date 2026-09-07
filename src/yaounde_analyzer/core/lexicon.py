"""Curated lexicon contracts: the reviewed dictionary the lexer matches against.

Regex scanning (see text.py) finds candidate word/number spans; this module defines
the vocabulary that classifies those spans into Francanglais terminals and part-of-speech
tags. Coverage is corpus-driven: an entry only exists here because it is attested in a
reviewed statement, not because it completes a general-purpose French or English lexicon.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from yaounde_analyzer.core.models import LanguageLabel
from yaounde_analyzer.core.scope import FrancanglaisModel
from yaounde_analyzer.core.text import canonicalize_word


class LexicalEntry(FrancanglaisModel):
    """One dictionary entry: a canonical word or fixed multiword phrase and its category."""

    canonical: str = Field(min_length=1)
    terminal: str
    part_of_speech: str
    is_slang: bool = False
    language_candidates: tuple[LanguageLabel, ...] = (LanguageLabel.UNCERTAIN,)
    rule_id: str
    evidence_statement_ids: tuple[str, ...] = ()
    description: str = ""

    @property
    def words(self) -> tuple[str, ...]:
        """The entry's canonical form split into its constituent words."""
        return tuple(self.canonical.split(" "))

    @model_validator(mode="after")
    def _check_canonical_is_normalized(self) -> LexicalEntry:
        words = self.canonical.split(" ")
        if any(not word for word in words):
            raise ValueError(f"entry {self.rule_id!r} canonical form has extra whitespace")
        normalized = " ".join(canonicalize_word(word) for word in words)
        if normalized != self.canonical:
            raise ValueError(
                f"entry {self.rule_id!r} canonical form {self.canonical!r} is not "
                f"normalized; expected {normalized!r}"
            )
        return self


class LexiconSpec(FrancanglaisModel):
    """The full curated dictionary used to classify word spans during tokenization."""

    version: str
    entries: tuple[LexicalEntry, ...]

    @model_validator(mode="after")
    def _check_entries_are_well_formed(self) -> LexiconSpec:
        seen_canonical: set[str] = set()
        seen_rule_ids: set[str] = set()
        for entry in self.entries:
            if entry.canonical in seen_canonical:
                raise ValueError(f"duplicate lexicon entry for canonical form {entry.canonical!r}")
            seen_canonical.add(entry.canonical)
            if entry.rule_id in seen_rule_ids:
                raise ValueError(f"duplicate lexicon rule_id {entry.rule_id!r}")
            seen_rule_ids.add(entry.rule_id)
        return self

    def single_word_lookup(self) -> dict[str, LexicalEntry]:
        """Entries whose canonical form is exactly one word, keyed by that word."""
        return {entry.canonical: entry for entry in self.entries if len(entry.words) == 1}

    def multiword_entries_by_first_word(self) -> dict[str, tuple[LexicalEntry, ...]]:
        """Multiword entries grouped by their first word, longest word-count first.

        Ordering longest-first lets the lexer try the most specific phrase before
        falling back to shorter phrases or a plain single-word match.
        """
        by_first_word: dict[str, list[LexicalEntry]] = {}
        for entry in self.entries:
            words = entry.words
            if len(words) > 1:
                by_first_word.setdefault(words[0], []).append(entry)
        return {
            first_word: tuple(sorted(entries, key=lambda e: len(e.words), reverse=True))
            for first_word, entries in by_first_word.items()
        }
