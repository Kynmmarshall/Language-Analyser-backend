"""Explicit-stack, table-driven LL(1) parser.

Consumes the actual lexer Token stream against a GrammarSpec and its LL1Table (see
ll1.py). Accepts only when the stack and input both finish together; distinguishes
lexical rejection (an UNKNOWN token), syntactic rejection (no table entry / terminal
mismatch, or unconsumed trailing input), and resource-limit rejection (bounded execution).
"""

from __future__ import annotations

from yaounde_analyzer.core.lexer import UNKNOWN_TERMINAL
from yaounde_analyzer.core.ll1 import LL1Table
from yaounde_analyzer.core.models import (
    EOF,
    GrammarSpec,
    ParserAction,
    ParseResult,
    ParseTreeNode,
    RejectionReason,
    SourceSpan,
    Token,
    TraceStep,
)

DEFAULT_MAX_STEPS = 10_000
DEFAULT_MAX_STACK_DEPTH = 500


class ParserConfigurationError(ValueError):
    """Raised when asked to parse against a grammar/table that is not valid LL(1).

    This is a configuration error, checked once when the analyzer starts up, and is
    distinct from a ParseResult rejection of a particular input.
    """


class _MutableNode:
    """A parse-tree node under construction; frozen into ParseTreeNode once parsing ends."""

    __slots__ = ("symbol", "production_id", "token_span", "children")

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.production_id: str | None = None
        self.token_span: SourceSpan | None = None
        self.children: list[_MutableNode] = []

    def freeze(self) -> ParseTreeNode:
        return ParseTreeNode(
            symbol=self.symbol,
            production_id=self.production_id,
            token_span=self.token_span,
            children=tuple(child.freeze() for child in self.children),
        )


def parse_tokens(
    tokens: tuple[Token, ...],
    grammar: GrammarSpec,
    table: LL1Table,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_stack_depth: int = DEFAULT_MAX_STACK_DEPTH,
) -> ParseResult:
    if not table.is_ll1:
        raise ParserConfigurationError(
            f"grammar {grammar.version!r} has unresolved LL(1) table conflicts and cannot "
            "be used to parse; fix the grammar before analyzing statements"
        )

    first_unknown = next((t for t in tokens if t.terminal == UNKNOWN_TERMINAL), None)
    if first_unknown is not None:
        return ParseResult(
            accepted=False,
            rejection_reason=RejectionReason.LEXICAL_UNKNOWN_TOKEN,
            failing_position=first_unknown.span.start,
            expected_terminals=(),
        )

    productions_by_id = {p.id: p for p in grammar.productions}
    terminal_symbols = tuple(t.terminal for t in tokens)

    root = _MutableNode(grammar.start_symbol)
    stack: list[tuple[str, _MutableNode | None]] = [(EOF, None), (grammar.start_symbol, root)]
    trace: list[TraceStep] = []
    applied: list[str] = []
    input_index = 0
    step = 0

    def lookahead() -> str:
        return terminal_symbols[input_index] if input_index < len(terminal_symbols) else EOF

    def failing_position() -> int | None:
        if input_index < len(tokens):
            return tokens[input_index].span.start
        return tokens[-1].span.end if tokens else None

    def remaining() -> tuple[str, ...]:
        return (*terminal_symbols[input_index:], EOF)

    while stack:
        step += 1
        if step > max_steps or len(stack) > max_stack_depth:
            return ParseResult(
                accepted=False,
                rejection_reason=RejectionReason.RESOURCE_LIMIT_EXCEEDED,
                matched_token_count=input_index,
                failing_position=failing_position(),
                applied_production_ids=tuple(applied),
                trace=tuple(trace),
            )

        top_symbol, top_node = stack[-1]
        current = lookahead()
        stack_symbols = tuple(symbol for symbol, _ in stack)

        if top_symbol == EOF:
            if current == EOF:
                trace.append(
                    TraceStep(
                        step=step, stack=stack_symbols, remaining_terminals=remaining(),
                        action=ParserAction.ACCEPT,
                    )
                )
                stack.pop()
                break
            return ParseResult(
                accepted=False,
                rejection_reason=RejectionReason.SYNTAX_TRAILING_INPUT,
                matched_token_count=input_index,
                failing_position=failing_position(),
                expected_terminals=(EOF,),
                applied_production_ids=tuple(applied),
                trace=tuple(trace),
            )

        if top_symbol in grammar.terminals:
            if current == top_symbol:
                token = tokens[input_index]
                assert top_node is not None  # every non-EOF stack frame carries a node
                top_node.token_span = SourceSpan(start=token.span.start, end=token.span.end)
                trace.append(
                    TraceStep(
                        step=step, stack=stack_symbols, remaining_terminals=remaining(),
                        action=ParserAction.MATCH,
                    )
                )
                stack.pop()
                input_index += 1
                continue
            return ParseResult(
                accepted=False,
                rejection_reason=RejectionReason.SYNTAX_NO_TABLE_ENTRY,
                matched_token_count=input_index,
                failing_position=failing_position(),
                expected_terminals=(top_symbol,),
                applied_production_ids=tuple(applied),
                trace=tuple(trace),
            )

        # top_symbol is a nonterminal: consult the LL(1) table.
        production_id = table.entries.get((top_symbol, current))
        if production_id is None:
            expected = tuple(
                sorted(terminal for (nt, terminal) in table.entries if nt == top_symbol)
            )
            return ParseResult(
                accepted=False,
                rejection_reason=RejectionReason.SYNTAX_NO_TABLE_ENTRY,
                matched_token_count=input_index,
                failing_position=failing_position(),
                expected_terminals=expected,
                applied_production_ids=tuple(applied),
                trace=tuple(trace),
            )

        rule = productions_by_id[production_id]
        applied.append(production_id)
        trace.append(
            TraceStep(
                step=step, stack=stack_symbols, remaining_terminals=remaining(),
                action=ParserAction.EXPAND, production_id=production_id,
            )
        )
        stack.pop()
        assert top_node is not None
        top_node.production_id = production_id
        children = [_MutableNode(symbol) for symbol in rule.rhs]
        top_node.children = children
        for symbol, child in zip(reversed(rule.rhs), reversed(children), strict=True):
            stack.append((symbol, child))

    return ParseResult(
        accepted=True,
        matched_token_count=input_index,
        applied_production_ids=tuple(applied),
        trace=tuple(trace),
        tree=root.freeze(),
    )
