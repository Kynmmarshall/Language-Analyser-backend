"""Combines the lexer and parser into per-statement analysis, transparent topic matching,
and Counter-based corpus frequency/variation statistics.

Topic matching is a transparent, evidence-based label attached alongside grammatical
analysis; it never influences whether a statement is accepted or rejected.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from yaounde_analyzer.core.corpus import StatementRevision
from yaounde_analyzer.core.grammar import compute_nullable, prepare_grammar
from yaounde_analyzer.core.lexer import UNKNOWN_TERMINAL, tokenize
from yaounde_analyzer.core.lexicon import LexiconSpec
from yaounde_analyzer.core.ll1 import LL1Table, build_ll1_table, compute_first, compute_follow
from yaounde_analyzer.core.models import (
    AnalysisResult,
    GrammarSpec,
    ParseResult,
    Token,
    TopicMatch,
    TransformationStep,
)
from yaounde_analyzer.core.parser import ParserConfigurationError, parse_tokens

# Corpus-driven, evidence-based keyword rules. Each canonical word here is attested in the
# reviewed demo statements cited in specs/demo/lexicon.json descriptions; a topic is only
# ever reported together with the exact matched words, never as an opaque classification.
TOPIC_KEYWORDS: dict[str, frozenset[str]] = {
    "commuting": frozenset({"taximan", "taco", "course", "va", "waka"}),
    "internet": frozenset({"réseau", "message", "send", "phone"}),
    "electricity": frozenset({"courant", "coupé"}),
    "market_bargaining": frozenset({"prix", "baisse", "nkap", "dos", "buy", "tomates"}),
    "rain": frozenset({"pluie"}),
    "fuel": frozenset({"l'essence", "caisse", "à sec"}),
    "roadside_business": frozenset({"tchop", "poisson"}),
    "bendskin": frozenset({"bendskin"}),
    "security": frozenset({"vols", "garde"}),
    "university": frozenset({"school", "prof"}),
}


def match_topics(tokens: tuple[Token, ...]) -> tuple[TopicMatch, ...]:
    """Transparent topic labelling: a topic is reported only with its matched canonical
    words, so a reviewer can see exactly why it was attached. A statement may match
    several topics, or none; this never affects grammatical acceptance.
    """
    canonical_forms = [token.canonical for token in tokens]
    matches = [
        TopicMatch(
            topic=topic,
            matched_terms=tuple(sorted({c for c in canonical_forms if c in keywords})),
        )
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(c in keywords for c in canonical_forms)
    ]
    return tuple(sorted(matches, key=lambda m: m.topic))


class PreparedAnalyzer:
    """A lexicon + executable grammar + precomputed LL(1) table, built once and reused.

    `descriptive_grammar` is the corpus-derived grammar as authored; `grammar` is the
    executable form after left-recursion elimination and left-factoring (see grammar.py),
    which is what the parser and table actually reference. `transformation_steps` is the
    visible before/after ledger for that preparation.
    """

    def __init__(self, lexicon: LexiconSpec, grammar: GrammarSpec) -> None:
        self.lexicon = lexicon
        self.descriptive_grammar = grammar
        prepared = prepare_grammar(grammar)
        self.grammar = prepared.grammar
        self.transformation_steps: tuple[TransformationStep, ...] = prepared.steps
        nullable = compute_nullable(self.grammar)
        first = compute_first(self.grammar, nullable)
        follow = compute_follow(self.grammar, first, nullable)
        self.table: LL1Table = build_ll1_table(self.grammar, first, follow, nullable)

    def check(self) -> None:
        """Raise ParserConfigurationError now if the grammar is not valid LL(1)."""
        if not self.table.is_ll1:
            raise ParserConfigurationError(
                f"grammar {self.grammar.version!r} has unresolved LL(1) table conflicts: "
                f"{self.table.conflicts}"
            )


def analyze_tokens_and_parse(
    text: str, analyzer: PreparedAnalyzer
) -> tuple[tuple[Token, ...], ParseResult, tuple[TopicMatch, ...]]:
    """Tokenize and parse raw text against a prepared analyzer, without any storage tie-in."""
    tokens = tokenize(text, analyzer.lexicon)
    parse = parse_tokens(tokens, analyzer.grammar, analyzer.table)
    topics = match_topics(tokens)
    return tokens, parse, topics


def analyze_statement(revision: StatementRevision, analyzer: PreparedAnalyzer) -> AnalysisResult:
    """Analyze one stored statement revision, tying the result to its exact revision."""
    tokens, parse, topics = analyze_tokens_and_parse(revision.raw_text, analyzer)
    return AnalysisResult(
        statement_revision_id=f"{revision.statement_id}@{revision.revision}",
        tokens=tokens,
        parse=parse,
        topics=topics,
    )


def analyze_corpus(
    revisions: Sequence[StatementRevision], analyzer: PreparedAnalyzer
) -> tuple[AnalysisResult, ...]:
    return tuple(analyze_statement(revision, analyzer) for revision in revisions)


@dataclass(frozen=True)
class CorpusStatistics:
    """Frequency/variation and acceptance counts over a batch of analysis results."""

    statement_count: int
    accepted_count: int
    rejected_count: int
    raw_frequency: dict[str, int]
    canonical_frequency: dict[str, int]
    terminal_frequency: dict[str, int]
    unknown_words: tuple[str, ...]


def compute_statistics(results: tuple[AnalysisResult, ...]) -> CorpusStatistics:
    raw_counts: Counter[str] = Counter()
    canonical_counts: Counter[str] = Counter()
    terminal_counts: Counter[str] = Counter()
    unknown_words: set[str] = set()
    accepted = 0

    for result in results:
        if result.parse.accepted:
            accepted += 1
        for token in result.tokens:
            raw_counts[token.raw] += 1
            canonical_counts[token.canonical] += 1
            terminal_counts[token.terminal] += 1
            if token.terminal == UNKNOWN_TERMINAL:
                unknown_words.add(token.raw)

    return CorpusStatistics(
        statement_count=len(results),
        accepted_count=accepted,
        rejected_count=len(results) - accepted,
        raw_frequency=dict(raw_counts),
        canonical_frequency=dict(canonical_counts),
        terminal_frequency=dict(terminal_counts),
        unknown_words=tuple(sorted(unknown_words)),
    )
