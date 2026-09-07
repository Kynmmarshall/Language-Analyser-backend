"""FIRST/FOLLOW/SELECT computation and LL(1) parsing table construction.

Operates on an already-transformed (left-recursion-eliminated, left-factored) GrammarSpec.
Nullable computation is reused from grammar.py rather than recomputed here, since it is
needed earlier in the pipeline (left-recursion detection happens before FIRST/FOLLOW).
"""

from __future__ import annotations

from dataclasses import dataclass

from yaounde_analyzer.core.models import EOF, GrammarSpec, Production

FirstSets = dict[str, frozenset[str]]
FollowSets = dict[str, frozenset[str]]


def _productions_by_lhs(grammar: GrammarSpec) -> dict[str, tuple[Production, ...]]:
    by_lhs: dict[str, list[Production]] = {nt: [] for nt in grammar.nonterminals}
    for production in grammar.productions:
        by_lhs[production.lhs].append(production)
    return {lhs: tuple(rules) for lhs, rules in by_lhs.items()}


def compute_first(grammar: GrammarSpec, nullable: frozenset[str]) -> FirstSets:
    """FIRST(X) for every declared terminal and nonterminal X.

    A terminal's FIRST set is itself. A nonterminal's FIRST set is the union, over each
    of its productions, of the FIRST sets of RHS symbols up to (and including, if
    nullable) the first non-nullable symbol — computed to a monotone fixed point.
    """
    first: dict[str, set[str]] = {terminal: {terminal} for terminal in grammar.terminals}
    for nonterminal in grammar.nonterminals:
        first[nonterminal] = set()
    by_lhs = _productions_by_lhs(grammar)

    changed = True
    while changed:
        changed = False
        for nonterminal, rules in by_lhs.items():
            for rule in rules:
                before = len(first[nonterminal])
                for symbol in rule.rhs:
                    first[nonterminal] |= first[symbol]
                    if symbol not in nullable:
                        break
                if len(first[nonterminal]) != before:
                    changed = True
    return {symbol: frozenset(values) for symbol, values in first.items()}


def first_of_sequence(
    sequence: tuple[str, ...], first: FirstSets, nullable: frozenset[str]
) -> frozenset[str]:
    """FIRST of a full RHS symbol sequence, honoring nullable prefixes.

    An empty sequence (an epsilon production) has an empty FIRST set here by definition;
    epsilon itself is never added to a FIRST set or used as a lookahead symbol.
    """
    result: set[str] = set()
    for symbol in sequence:
        result |= first.get(symbol, frozenset())
        if symbol not in nullable:
            return frozenset(result)
    return frozenset(result)


def compute_follow(grammar: GrammarSpec, first: FirstSets, nullable: frozenset[str]) -> FollowSets:
    """FOLLOW(A) for every nonterminal A, computed to a monotone fixed point.

    FOLLOW(start) is seeded with EOF; EOF never appears in any FIRST set or RHS, so it can
    only enter a FOLLOW set here or by propagation from the start symbol's FOLLOW set.
    """
    follow: dict[str, set[str]] = {nonterminal: set() for nonterminal in grammar.nonterminals}
    follow[grammar.start_symbol].add(EOF)

    changed = True
    while changed:
        changed = False
        for rule in grammar.productions:
            for index, symbol in enumerate(rule.rhs):
                if symbol not in grammar.nonterminals:
                    continue
                beta = rule.rhs[index + 1 :]
                beta_first = first_of_sequence(beta, first, nullable)
                before = len(follow[symbol])
                follow[symbol] |= beta_first
                if all(s in nullable for s in beta):
                    follow[symbol] |= follow[rule.lhs]
                if len(follow[symbol]) != before:
                    changed = True
    return {symbol: frozenset(values) for symbol, values in follow.items()}


@dataclass(frozen=True)
class TableConflict:
    """Two or more productions claim the same (nonterminal, lookahead) table cell."""

    nonterminal: str
    terminal: str
    production_ids: tuple[str, ...]


@dataclass(frozen=True)
class LL1Table:
    """The LL(1) parsing table. `entries` only contains conflict-free cells."""

    entries: dict[tuple[str, str], str]
    conflicts: tuple[TableConflict, ...]

    @property
    def is_ll1(self) -> bool:
        """True if the grammar produced no FIRST/FIRST or FIRST/FOLLOW conflicts."""
        return not self.conflicts


def build_ll1_table(
    grammar: GrammarSpec, first: FirstSets, follow: FollowSets, nullable: frozenset[str]
) -> LL1Table:
    """Build the LL(1) table's SELECT-set cells, reporting rather than resolving conflicts.

    For each production A -> alpha, SELECT(A -> alpha) is FIRST(alpha), plus FOLLOW(A) if
    alpha is entirely nullable. A cell claimed by more than one production is a genuine
    ambiguity (FIRST/FIRST if both claims come from FIRST(alpha), FIRST/FOLLOW if one claim
    comes from an epsilon-like production's FOLLOW set) and is never silently resolved by
    picking the first production; it is reported in `conflicts` and left out of `entries`.
    """
    claims: dict[tuple[str, str], list[str]] = {}
    for rule in grammar.productions:
        select = set(first_of_sequence(rule.rhs, first, nullable))
        if all(symbol in nullable for symbol in rule.rhs):
            select |= follow[rule.lhs]
        for terminal in select:
            claims.setdefault((rule.lhs, terminal), []).append(rule.id)

    entries: dict[tuple[str, str], str] = {}
    conflicts: list[TableConflict] = []
    for (nonterminal, terminal), production_ids in claims.items():
        if len(production_ids) > 1:
            conflicts.append(TableConflict(nonterminal, terminal, tuple(production_ids)))
        else:
            entries[(nonterminal, terminal)] = production_ids[0]
    return LL1Table(entries=entries, conflicts=tuple(conflicts))
