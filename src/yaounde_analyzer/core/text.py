"""Shared Unicode-aware text scanning primitives used by the lexer and lexicon."""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import NamedTuple

# A "word" is one or more letters (any Unicode letter, via \W/\d/_ exclusion) or combining
# marks (needed because Python's \w does not include NFD combining diacritics, e.g. "a" +
# U+0300 for a decomposed "à"), optionally joined by a single apostrophe or hyphen followed
# by more letters, so "j'ai" and "franc-anglais" are each one span, and both NFC and NFD
# spellings of an accented word stay a single span with their original code points intact.
_LETTER_RUN = r"(?:[^\W\d_]|[\u0300-\u036f])+"
_WORD_RE = re.compile(rf"{_LETTER_RUN}(?:['\u2019-]{_LETTER_RUN})*")
_NUMBER_RE = re.compile(r"\d+")
_NEWLINE_RE = re.compile(r"[\r\n]+")
_SPACE_RE = re.compile(r"[^\S\r\n]+")
_PUNCTUATION_RE = re.compile(r"[.,!?;:\"()«»\u2018\u2019\u201c\u201d…]+")


class SpanKind(StrEnum):
    WORD = "word"
    NUMBER = "number"
    SPACE = "space"
    NEWLINE = "newline"
    PUNCTUATION = "punctuation"
    OTHER = "other"


class RawSpan(NamedTuple):
    """One maximal-length span of a single kind, with code-point offsets into the source text."""

    kind: SpanKind
    start: int
    end: int
    raw: str


def canonicalize_word(word: str) -> str:
    """Normalize a raw word span to its lexicon lookup form (NFC, case-folded).

    Applied only to matched word spans for dictionary lookup; the original raw text and
    its offsets are always preserved separately and are never overwritten by this form.
    """
    return unicodedata.normalize("NFC", word).casefold()


def scan_spans(text: str) -> tuple[RawSpan, ...]:
    """Split text into maximal WORD/NUMBER/SPACE/NEWLINE/PUNCTUATION/OTHER spans.

    Every code point in `text` is covered by exactly one span, in order, with no gaps
    and no overlaps: the lexer's tokenizer can rely on this to guarantee it always
    advances and never loses or duplicates source text.
    """
    spans: list[RawSpan] = []
    position = 0
    length = len(text)
    while position < length:
        for kind, pattern in (
            (SpanKind.WORD, _WORD_RE),
            (SpanKind.NUMBER, _NUMBER_RE),
            (SpanKind.NEWLINE, _NEWLINE_RE),
            (SpanKind.SPACE, _SPACE_RE),
            (SpanKind.PUNCTUATION, _PUNCTUATION_RE),
        ):
            match = pattern.match(text, position)
            if match:
                spans.append(RawSpan(kind, match.start(), match.end(), match.group()))
                position = match.end()
                break
        else:
            # No pattern matched: consume exactly one unsupported code point so the
            # scanner always makes progress instead of looping or skipping input.
            spans.append(RawSpan(SpanKind.OTHER, position, position + 1, text[position]))
            position += 1
    return tuple(spans)
