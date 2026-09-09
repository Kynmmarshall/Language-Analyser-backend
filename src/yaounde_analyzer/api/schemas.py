"""API-layer request/response schemas.

Reuses core.models directly for analysis output (Token, ParseResult, TopicMatch) so the
API never duplicates or reshapes what the compiler actually produced. Statement schemas
are API-specific because they must enforce a public/private projection boundary that the
storage-independent core.corpus.StatementRevision does not itself impose.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from yaounde_analyzer.core.lexicon import LexicalEntry
from yaounde_analyzer.core.models import (
    GrammarSpec,
    ParseResult,
    Token,
    TopicMatch,
    TransformationStep,
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tokens: tuple[Token, ...]
    parse: ParseResult
    topics: tuple[TopicMatch, ...]


class StatementCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement_id: str = Field(min_length=1, max_length=64)
    source_kind: str = Field(pattern="^(demo|field)$")
    raw_text: str = Field(min_length=1, max_length=2000)
    manual_transcription_attested: bool
    collector_id: str = Field(min_length=1, max_length=64)
    topics: tuple[str, ...] = ()


class StatementUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    raw_text: str = Field(min_length=1, max_length=2000)
    source_kind: str = Field(pattern="^(demo|field)$")
    manual_transcription_attested: bool
    collector_id: str = Field(min_length=1, max_length=64)
    topics: tuple[str, ...] = ()


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)


class StatementPrivate(BaseModel):
    """Full protected view of a statement's current (latest) revision."""

    model_config = ConfigDict(extra="forbid")
    statement_id: str
    revision: int
    source_kind: str
    raw_text: str
    manual_transcription_attested: bool
    collector_id: str
    topics: tuple[str, ...]
    created_at: datetime
    published_revision: int | None


class StatementRevisionHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int
    source_kind: str
    raw_text: str
    manual_transcription_attested: bool
    collector_id: str
    topics: tuple[str, ...]
    created_at: datetime
    created_by: str | None


class StatementPublic(BaseModel):
    """The only view an anonymous visitor may ever see: the approved-public projection."""

    model_config = ConfigDict(extra="forbid")
    statement_id: str
    raw_text: str
    topics: tuple[str, ...]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detail: str


class TableEntry(BaseModel):
    """One conflict-free LL(1) table cell."""

    model_config = ConfigDict(extra="forbid")
    nonterminal: str
    terminal: str
    production_id: str


class TableConflictView(BaseModel):
    """A table cell claimed by more than one production; never silently resolved."""

    model_config = ConfigDict(extra="forbid")
    nonterminal: str
    terminal: str
    production_ids: tuple[str, ...]


class SymbolSet(BaseModel):
    """One row of a FIRST/FOLLOW/nullable table, keyed by grammar symbol."""

    model_config = ConfigDict(extra="forbid")
    symbol: str
    terminals: tuple[str, ...]


class GrammarView(BaseModel):
    """Everything the Grammar screen needs: lexicon, original/transformed rules, the
    transformation ledger, nullable/FIRST/FOLLOW sets, and the LL(1) table."""

    model_config = ConfigDict(extra="forbid")
    lexicon: tuple[LexicalEntry, ...]
    descriptive_grammar: GrammarSpec
    grammar: GrammarSpec
    transformation_steps: tuple[TransformationStep, ...]
    nullable: tuple[str, ...]
    first: tuple[SymbolSet, ...]
    follow: tuple[SymbolSet, ...]
    table_entries: tuple[TableEntry, ...]
    table_conflicts: tuple[TableConflictView, ...]
