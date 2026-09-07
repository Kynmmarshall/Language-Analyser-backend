"""Core, storage-independent data contracts shared by the lexer, grammar, and parser.

These are plain Pydantic models with no FastAPI, database, or network dependency.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EPSILON: tuple[str, ...] = ()
"""An empty RHS symbol sequence represents an epsilon production."""

EOF = "$"
"""Reserved end-of-input symbol. Never obtainable as a token from user text."""


class SourceSpan(BaseModel):
    """A half-open [start, end) range of Unicode code-point offsets into the raw statement text."""

    model_config = ConfigDict(frozen=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> SourceSpan:
        if self.end < self.start:
            raise ValueError(f"span end {self.end} precedes start {self.start}")
        return self


class LanguageLabel(StrEnum):
    """Independent language-origin annotation; never a claim of certainty without evidence."""

    ENGLISH = "english"
    FRENCH = "french"
    PIDGIN = "pidgin"
    FULFULDE = "fulfulde"
    EWONDO = "ewondo"
    MIXED = "mixed"
    UNCERTAIN = "uncertain"


class Token(BaseModel):
    """A single lexical token produced by the lexer, tied to its exact source span."""

    model_config = ConfigDict(frozen=True)

    raw: str
    canonical: str
    terminal: str
    part_of_speech: str
    language_candidates: tuple[LanguageLabel, ...] = (LanguageLabel.UNCERTAIN,)
    is_slang: bool = False
    is_multiword: bool = False
    component_spans: tuple[SourceSpan, ...] = ()
    rule_id: str
    span: SourceSpan

    @model_validator(mode="after")
    def _check_multiword_components(self) -> Token:
        if self.is_multiword and not self.component_spans:
            raise ValueError("multiword tokens must record their component spans")
        return self


class Production(BaseModel):
    """One grammar rule: lhs -> rhs (rhs empty means an epsilon production)."""

    model_config = ConfigDict(frozen=True)

    id: str
    lhs: str
    rhs: tuple[str, ...] = EPSILON
    evidence_statement_ids: tuple[str, ...] = ()
    description: str = ""


class GrammarSpec(BaseModel):
    """A structured, corpus-derived context-free grammar."""

    model_config = ConfigDict(frozen=True)

    version: str
    start_symbol: str
    terminals: tuple[str, ...]
    nonterminals: tuple[str, ...]
    productions: tuple[Production, ...]

    @model_validator(mode="after")
    def _check_symbols(self) -> GrammarSpec:
        overlap = set(self.terminals) & set(self.nonterminals)
        if overlap:
            raise ValueError(f"terminals and nonterminals must be disjoint, overlap: {overlap}")
        if self.start_symbol not in self.nonterminals:
            raise ValueError(f"start symbol {self.start_symbol!r} is not a declared nonterminal")
        known = set(self.terminals) | set(self.nonterminals)
        seen_ids: set[str] = set()
        for production in self.productions:
            if production.id in seen_ids:
                raise ValueError(f"duplicate production id {production.id!r}")
            seen_ids.add(production.id)
            if production.lhs not in self.nonterminals:
                raise ValueError(
                    f"production {production.id!r} has undeclared lhs {production.lhs!r}"
                )
            unknown = [s for s in production.rhs if s not in known]
            if unknown:
                raise ValueError(
                    f"production {production.id!r} references undeclared symbols {unknown}"
                )
        return self


class TransformationKind(StrEnum):
    LEFT_RECURSION_ELIMINATION = "left_recursion_elimination"
    LEFT_FACTORING = "left_factoring"


class TransformationStep(BaseModel):
    """One reviewable step in the descriptive-to-executable grammar transformation ledger."""

    model_config = ConfigDict(frozen=True)

    kind: TransformationKind
    description: str
    source_production_ids: tuple[str, ...]
    result_production_ids: tuple[str, ...]


class ParserAction(StrEnum):
    PUSH = "push"
    MATCH = "match"
    EXPAND = "expand"
    ACCEPT = "accept"
    REJECT = "reject"


class TraceStep(BaseModel):
    """One recorded step of the explicit-stack LL(1) parser."""

    model_config = ConfigDict(frozen=True)

    step: int = Field(ge=0)
    stack: tuple[str, ...]
    remaining_terminals: tuple[str, ...]
    action: ParserAction
    production_id: str | None = None


class RejectionReason(StrEnum):
    LEXICAL_UNKNOWN_TOKEN = "lexical_unknown_token"
    SYNTAX_NO_TABLE_ENTRY = "syntax_no_table_entry"
    SYNTAX_TRAILING_INPUT = "syntax_trailing_input"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"


class ParseTreeNode(BaseModel):
    """A parse tree node; terminal nodes reference a token, nonterminal nodes a production."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    production_id: str | None = None
    token_span: SourceSpan | None = None
    children: tuple[ParseTreeNode, ...] = ()


class ParseResult(BaseModel):
    """Outcome of parsing one tokenized statement against the LL(1) table."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    rejection_reason: RejectionReason | None = None
    matched_token_count: int = Field(ge=0, default=0)
    failing_position: int | None = None
    expected_terminals: tuple[str, ...] = ()
    applied_production_ids: tuple[str, ...] = ()
    trace: tuple[TraceStep, ...] = ()
    tree: ParseTreeNode | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> ParseResult:
        if self.accepted and self.rejection_reason is not None:
            raise ValueError("an accepted result must not carry a rejection reason")
        if not self.accepted and self.rejection_reason is None:
            raise ValueError("a rejected result must carry a rejection reason")
        return self


class TopicMatch(BaseModel):
    """A transparent, evidence-based topic label for a statement."""

    model_config = ConfigDict(frozen=True)

    topic: str
    matched_terms: tuple[str, ...]


class AnalysisResult(BaseModel):
    """Combined lexical and syntactic analysis of a single statement revision."""

    model_config = ConfigDict(frozen=True)

    statement_revision_id: str
    tokens: tuple[Token, ...]
    parse: ParseResult
    topics: tuple[TopicMatch, ...] = ()


SourceKind = Literal["demo", "field"]
