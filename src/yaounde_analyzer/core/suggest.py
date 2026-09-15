"""Deterministic repair hints derived from the parser's own failure report.

No model or network call is involved. An unrecognised word is matched against the
lexicon by string similarity, and a syntax failure is explained from the terminals the
LL(1) table expected at that position, so identical input always yields identical advice
and the recorded analysis stays reproducible.
"""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel, ConfigDict

from yaounde_analyzer.core.lexer import UNKNOWN_TERMINAL
from yaounde_analyzer.core.lexicon import LexiconSpec
from yaounde_analyzer.core.models import ParseResult, RejectionReason, SourceSpan, Token
from yaounde_analyzer.core.text import fold_word

MAX_REPLACEMENTS = 5
MAX_EXAMPLES = 3
EOF_SYMBOL = "$"
_SIMILARITY_CUTOFF = 0.6


class Suggestion(BaseModel):
    """One actionable hint about why a statement was not accepted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["unknown_word", "unexpected_token", "trailing_input"]
    message: str
    span: SourceSpan | None = None
    replacements: tuple[str, ...] = ()


def _closest_canonicals(word: str, lexicon: LexiconSpec) -> tuple[str, ...]:
    # Compared on folded forms so a missing accent cannot hide an otherwise close match.
    by_folded = {fold_word(entry.canonical): entry.canonical for entry in lexicon.entries}
    matches = difflib.get_close_matches(
        fold_word(word), list(by_folded), n=MAX_REPLACEMENTS, cutoff=_SIMILARITY_CUTOFF
    )
    return tuple(by_folded[match] for match in matches)


def _examples_for(terminals: tuple[str, ...], lexicon: LexiconSpec) -> tuple[str, ...]:
    examples: list[str] = []
    for terminal in terminals:
        if terminal == EOF_SYMBOL:
            continue
        found = [e.canonical for e in lexicon.entries if e.terminal == terminal]
        examples.extend(found[:MAX_EXAMPLES])
    return tuple(examples)


def _describe_expected(terminals: tuple[str, ...]) -> str:
    listed = [t for t in terminals if t != EOF_SYMBOL]
    if not listed:
        return "the end of the statement"
    if len(listed) == 1:
        return f"a {listed[0]}"
    return "a " + ", ".join(listed[:-1]) + f" or {listed[-1]}"


def _homograph_hints(
    tokens: tuple[Token, ...], lexicon: LexiconSpec
) -> list[Suggestion]:
    """Flag words in the failing span that have an accented twin the lexer cannot guess.

    'la'/'là' and 'a'/'à' are different words, so the lexer always takes the spelling as
    written; when that reading blocks the parse the other one is usually what was meant.
    """
    homographs = lexicon.homographs()
    hints: list[Suggestion] = []
    seen: set[str] = set()
    for token in tokens:
        alternatives = homographs.get(token.canonical)
        if not alternatives or token.canonical in seen:
            continue
        seen.add(token.canonical)
        spellings = ", ".join(f"'{a.canonical}' ({a.terminal})" for a in alternatives)
        hints.append(
            Suggestion(
                kind="unknown_word",
                message=(
                    f"'{token.raw}' was read as {token.terminal}. Written with its accent "
                    f"it would be {spellings} instead."
                ),
                span=token.span,
                replacements=tuple(a.canonical for a in alternatives),
            )
        )
    return hints


def suggest_fixes(
    tokens: tuple[Token, ...], parse: ParseResult, lexicon: LexiconSpec
) -> tuple[Suggestion, ...]:
    """Hints explaining why `parse` failed, or nothing at all when it succeeded."""
    if parse.accepted or parse.rejection_reason is None:
        return ()

    if parse.rejection_reason is RejectionReason.LEXICAL_UNKNOWN_TOKEN:
        return tuple(
            Suggestion(
                kind="unknown_word",
                message=f"'{token.raw}' is not in the lexicon.",
                span=token.span,
                replacements=_closest_canonicals(token.raw, lexicon),
            )
            for token in tokens
            if token.terminal == UNKNOWN_TERMINAL
        )

    index = parse.matched_token_count
    blocking = tokens[index] if index < len(tokens) else None

    if parse.rejection_reason is RejectionReason.SYNTAX_TRAILING_INPUT:
        where = f" starting at '{blocking.raw}'" if blocking else ""
        return (
            Suggestion(
                kind="trailing_input",
                message=(
                    f"The grammar matched the first {index} word(s) but could not attach "
                    f"the rest{where}. Split this into separate statements, or join the "
                    "clauses with a comma or a conjunction."
                ),
                span=blocking.span if blocking else None,
            ),
        )

    if parse.rejection_reason is RejectionReason.SYNTAX_NO_TABLE_ENTRY:
        subject = f"'{blocking.raw}'" if blocking else "the end of the statement"
        hints = [
            Suggestion(
                kind="unexpected_token",
                message=(
                    f"The grammar cannot continue at {subject}; it expected "
                    f"{_describe_expected(parse.expected_terminals)} here."
                ),
                span=blocking.span if blocking else None,
                replacements=_examples_for(parse.expected_terminals, lexicon),
            )
        ]
        hints.extend(_homograph_hints(tokens[: index + 1], lexicon))
        return tuple(hints)

    return ()
