"""Tokenizer: turns raw statement text into a stream of Francanglais tokens.

Regex scanning (text.py) finds candidate spans; this module classifies WORD spans
against the curated lexicon (lexicon.py), preferring the longest matching multiword
phrase, then falls back to a single-word lookup, then to an explicit UNKNOWN token.
Unknown vocabulary is preserved and returned, never silently dropped or guessed at.
"""

from __future__ import annotations

from yaounde_analyzer.core.lexicon import LexicalEntry, LexiconSpec
from yaounde_analyzer.core.models import SourceSpan, Token
from yaounde_analyzer.core.text import RawSpan, SpanKind, canonicalize_word, scan_spans

UNKNOWN_TERMINAL = "UNKNOWN"
NUMBER_TERMINAL = "NUMBER"
_TRIVIA_KINDS = frozenset({SpanKind.SPACE, SpanKind.NEWLINE, SpanKind.PUNCTUATION})


def _match_multiword(
    spans: tuple[RawSpan, ...], start: int, entry: LexicalEntry
) -> tuple[int, int] | None:
    """Try to match `entry`'s words starting at `spans[start]`.

    Consecutive words in a multiword entry must be separated by exactly one plain SPACE
    span; a PUNCTUATION or NEWLINE span in between blocks the match, so phrases are never
    matched across sentence boundaries or unrelated punctuation.

    Returns (index just past the match, end code-point offset), or None if it fails.
    """
    words = entry.words
    index = start
    for position, expected in enumerate(words):
        if index >= len(spans) or spans[index].kind != SpanKind.WORD:
            return None
        if canonicalize_word(spans[index].raw) != expected:
            return None
        end_offset = spans[index].end
        index += 1
        is_last_word = position == len(words) - 1
        if not is_last_word:
            if index >= len(spans) or spans[index].kind != SpanKind.SPACE:
                return None
            index += 1
    return index, end_offset


def _entry_token(text: str, entry: LexicalEntry, spans: tuple[RawSpan, ...]) -> Token:
    is_multiword = len(spans) > 1
    component_spans = (
        tuple(SourceSpan(start=span.start, end=span.end) for span in spans)
        if is_multiword
        else ()
    )
    start, end = spans[0].start, spans[-1].end
    return Token(
        raw=text[start:end],
        canonical=entry.canonical,
        terminal=entry.terminal,
        part_of_speech=entry.part_of_speech,
        language_candidates=entry.language_candidates,
        is_slang=entry.is_slang,
        is_multiword=is_multiword,
        component_spans=component_spans,
        rule_id=entry.rule_id,
        span=SourceSpan(start=start, end=end),
    )


def _unknown_token(text: str, span: RawSpan) -> Token:
    return Token(
        raw=text[span.start : span.end],
        canonical=canonicalize_word(span.raw) if span.kind == SpanKind.WORD else span.raw,
        terminal=UNKNOWN_TERMINAL,
        part_of_speech=UNKNOWN_TERMINAL,
        rule_id="lexer.unknown",
        span=SourceSpan(start=span.start, end=span.end),
    )


def _number_token(text: str, span: RawSpan) -> Token:
    return Token(
        raw=span.raw,
        canonical=span.raw,
        terminal=NUMBER_TERMINAL,
        part_of_speech=NUMBER_TERMINAL,
        rule_id="lexer.number",
        span=SourceSpan(start=span.start, end=span.end),
    )


def tokenize(text: str, lexicon: LexiconSpec) -> tuple[Token, ...]:
    """Tokenize `text` against `lexicon`, skipping trivia and preserving unknown words.

    Every code point of `text` is accounted for by exactly one scanned span (see
    scan_spans); this function only decides which spans become Tokens (WORD and NUMBER
    spans) and which are silently-skipped trivia (SPACE, NEWLINE, PUNCTUATION). It never
    invents, reorders, or drops a WORD/NUMBER span: unrecognized words become UNKNOWN
    tokens rather than being omitted from the returned stream.
    """
    spans = scan_spans(text)
    single_word_lookup = lexicon.single_word_lookup()
    multiword_by_first_word = lexicon.multiword_entries_by_first_word()

    tokens: list[Token] = []
    index = 0
    while index < len(spans):
        span = spans[index]
        if span.kind in _TRIVIA_KINDS:
            index += 1
            continue
        if span.kind == SpanKind.NUMBER:
            tokens.append(_number_token(text, span))
            index += 1
            continue
        # span.kind == SpanKind.WORD or SpanKind.OTHER from here.
        if span.kind != SpanKind.WORD:
            tokens.append(_unknown_token(text, span))
            index += 1
            continue

        canonical = canonicalize_word(span.raw)
        matched = False
        for candidate in multiword_by_first_word.get(canonical, ()):
            match = _match_multiword(spans, index, candidate)
            if match is not None:
                end_index, _ = match
                matched_spans = tuple(
                    s for s in spans[index:end_index] if s.kind == SpanKind.WORD
                )
                tokens.append(_entry_token(text, candidate, matched_spans))
                index = end_index
                matched = True
                break
        if matched:
            continue

        single_entry = single_word_lookup.get(canonical)
        if single_entry is not None:
            tokens.append(_entry_token(text, single_entry, (span,)))
        else:
            tokens.append(_unknown_token(text, span))
        index += 1

    return tuple(tokens)
