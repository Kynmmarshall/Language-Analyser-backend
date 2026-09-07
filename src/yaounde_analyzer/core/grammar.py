"""Grammar preparation: nullable analysis, left-recursion elimination, and left-factoring.

Transforms a descriptive GrammarSpec into an executable one, keeping every step in a
visible TransformationStep ledger. This module owns nullable computation (needed here to
detect left recursion hidden behind a nullable prefix); ll1.py reuses it rather than
recomputing it, since FIRST/FOLLOW/table construction happens after these transformations.
"""

from __future__ import annotations

from dataclasses import dataclass

from yaounde_analyzer.core.models import (
    EPSILON,
    GrammarSpec,
    Production,
    TransformationKind,
    TransformationStep,
)


class GrammarTransformError(ValueError):
    """Raised when a transformation's preconditions are not met (e.g. indirect recursion)."""


@dataclass(frozen=True)
class TransformResult:
    grammar: GrammarSpec
    steps: tuple[TransformationStep, ...]


def _productions_by_lhs(grammar: GrammarSpec) -> dict[str, tuple[Production, ...]]:
    by_lhs: dict[str, list[Production]] = {nt: [] for nt in grammar.nonterminals}
    for production in grammar.productions:
        by_lhs[production.lhs].append(production)
    return {lhs: tuple(rules) for lhs, rules in by_lhs.items()}


def compute_nullable(grammar: GrammarSpec) -> frozenset[str]:
    """Nonterminals that can derive the empty string, computed to a monotone fixed point."""
    by_lhs = _productions_by_lhs(grammar)
    nullable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for nonterminal, rules in by_lhs.items():
            if nonterminal in nullable:
                continue
            if any(all(symbol in nullable for symbol in rule.rhs) for rule in rules):
                nullable.add(nonterminal)
                changed = True
    return frozenset(nullable)


def find_unreachable_nonterminals(grammar: GrammarSpec) -> frozenset[str]:
    """Nonterminals never reachable from the start symbol through any production."""
    by_lhs = _productions_by_lhs(grammar)
    reachable = {grammar.start_symbol}
    frontier = [grammar.start_symbol]
    while frontier:
        current = frontier.pop()
        for rule in by_lhs.get(current, ()):
            for symbol in rule.rhs:
                if symbol in grammar.nonterminals and symbol not in reachable:
                    reachable.add(symbol)
                    frontier.append(symbol)
    return frozenset(grammar.nonterminals) - reachable


def find_unproductive_nonterminals(grammar: GrammarSpec) -> frozenset[str]:
    """Nonterminals that can never derive any string of terminals."""
    by_lhs = _productions_by_lhs(grammar)
    productive: set[str] = set()
    changed = True
    while changed:
        changed = False
        for nonterminal, rules in by_lhs.items():
            if nonterminal in productive:
                continue
            if any(
                all(s in grammar.terminals or s in productive for s in rule.rhs)
                for rule in rules
            ):
                productive.add(nonterminal)
                changed = True
    return frozenset(grammar.nonterminals) - productive


def find_left_recursive_cycles(grammar: GrammarSpec) -> tuple[tuple[str, ...], ...]:
    """Detect cycles in the nullable-aware left-corner graph.

    An edge X -> Y exists when some production X -> alpha Y ... has alpha (a possibly
    empty prefix of nonterminals) entirely nullable, i.e. Y can be the first symbol
    actually consumed when expanding X. A one-element cycle (A,) is direct left recursion
    (A -> A ...); a longer cycle is indirect left recursion, which this module detects but
    does not attempt to eliminate automatically.
    """
    nullable = compute_nullable(grammar)
    edges: dict[str, set[str]] = {nt: set() for nt in grammar.nonterminals}
    for production in grammar.productions:
        for symbol in production.rhs:
            if symbol not in grammar.nonterminals:
                break
            edges[production.lhs].add(symbol)
            if symbol not in nullable:
                break

    cycles: list[tuple[str, ...]] = []
    visited: set[str] = set()

    def visit(node: str, stack: list[str], on_stack: set[str]) -> None:
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(edges.get(node, ())):
            if neighbor in on_stack:
                start = stack.index(neighbor)
                cycles.append(tuple(stack[start:]))
            elif neighbor not in visited:
                visit(neighbor, stack, on_stack)
        stack.pop()
        on_stack.discard(node)
        visited.add(node)

    for start_node in grammar.nonterminals:
        if start_node not in visited:
            visit(start_node, [], set())
    return tuple(cycles)


def _fresh_nonterminal(base: str, used: set[str]) -> str:
    candidate = f"{base}'"
    while candidate in used:
        candidate += "'"
    return candidate


def eliminate_direct_left_recursion(grammar: GrammarSpec) -> TransformResult:
    """Eliminate direct left recursion A -> A a1 | ... | A an | b1 | ... | bm.

    Produces A -> b1 A' | ... | bm A' and A' -> a1 A' | ... | an A' | epsilon for every
    directly left-recursive nonterminal; nonterminals without direct left recursion are
    left untouched. Raises GrammarTransformError if any cycle in the grammar is indirect
    (length > 1) or if a directly recursive nonterminal has no non-recursive alternative,
    since neither case can be resolved by this transformation alone.
    """
    cycles = find_left_recursive_cycles(grammar)
    indirect = [cycle for cycle in cycles if len(cycle) > 1]
    if indirect:
        raise GrammarTransformError(
            "indirect left recursion is not supported by automatic elimination; found "
            f"cycles {indirect}. Rewrite the grammar to remove indirect recursion first."
        )
    direct_lhs = {cycle[0] for cycle in cycles if len(cycle) == 1}
    if not direct_lhs:
        return TransformResult(grammar=grammar, steps=())

    by_lhs = _productions_by_lhs(grammar)
    used_names = set(grammar.nonterminals)
    new_productions: list[Production] = []
    new_nonterminals: list[str] = []
    steps: list[TransformationStep] = []

    for lhs in grammar.nonterminals:
        rules = by_lhs[lhs]
        if lhs not in direct_lhs:
            new_productions.extend(rules)
            continue

        alpha_rules = [r for r in rules if r.rhs and r.rhs[0] == lhs]
        beta_rules = [r for r in rules if r not in alpha_rules]
        if not beta_rules:
            raise GrammarTransformError(
                f"nonterminal {lhs!r} is only left-recursive with no non-recursive "
                "alternative; elimination requires at least one A -> beta production"
            )

        tail = _fresh_nonterminal(lhs, used_names)
        used_names.add(tail)
        new_nonterminals.append(tail)

        beta_ids: list[str] = []
        for rule in beta_rules:
            new_id = f"{rule.id}.lr"
            new_productions.append(
                Production(
                    id=new_id,
                    lhs=lhs,
                    rhs=(*rule.rhs, tail),
                    evidence_statement_ids=rule.evidence_statement_ids,
                    description=f"left-recursion elimination: {rule.id} with {tail} appended",
                )
            )
            beta_ids.append(new_id)

        alpha_ids: list[str] = []
        for rule in alpha_rules:
            new_id = f"{rule.id}.tail"
            new_productions.append(
                Production(
                    id=new_id,
                    lhs=tail,
                    rhs=(*rule.rhs[1:], tail),
                    evidence_statement_ids=rule.evidence_statement_ids,
                    description=f"left-recursion elimination: tail derived from {rule.id}",
                )
            )
            alpha_ids.append(new_id)
        epsilon_id = f"{tail}.eps"
        new_productions.append(
            Production(
                id=epsilon_id,
                lhs=tail,
                rhs=EPSILON,
                description=f"left-recursion elimination: epsilon termination for {tail}",
            )
        )
        alpha_ids.append(epsilon_id)

        steps.append(
            TransformationStep(
                kind=TransformationKind.LEFT_RECURSION_ELIMINATION,
                description=(
                    f"Eliminated direct left recursion on {lhs!r} using fresh "
                    f"nonterminal {tail!r}"
                ),
                source_production_ids=tuple(r.id for r in (*beta_rules, *alpha_rules)),
                result_production_ids=tuple(beta_ids + alpha_ids),
            )
        )

    new_grammar = GrammarSpec(
        version=f"{grammar.version}+lr",
        start_symbol=grammar.start_symbol,
        terminals=grammar.terminals,
        nonterminals=(*grammar.nonterminals, *new_nonterminals),
        productions=tuple(new_productions),
    )
    return TransformResult(grammar=new_grammar, steps=tuple(steps))


def _longest_common_prefix_length(rules: list[Production]) -> int:
    shortest = min(len(rule.rhs) for rule in rules)
    length = 0
    while length < shortest and len({rule.rhs[length] for rule in rules}) == 1:
        length += 1
    return length


def left_factor(grammar: GrammarSpec) -> TransformResult:
    """Factor common RHS symbol prefixes among a nonterminal's alternatives.

    Groups alternatives by their first RHS symbol (the standard immediate left-factoring
    grouping); a group of two or more sharing a first symbol is factored on their full
    common prefix. Runs to a fixed point, since a factored remainder can itself expose a
    further common prefix worth factoring again.
    """
    productions = list(grammar.productions)
    used_names = set(grammar.nonterminals)
    new_nonterminals: list[str] = []
    steps: list[TransformationStep] = []

    changed = True
    while changed:
        changed = False
        by_lhs: dict[str, list[Production]] = {}
        for rule in productions:
            by_lhs.setdefault(rule.lhs, []).append(rule)

        for lhs, rules in by_lhs.items():
            groups: dict[str, list[Production]] = {}
            for rule in rules:
                if rule.rhs:
                    groups.setdefault(rule.rhs[0], []).append(rule)
            factorable = next((g for g in groups.values() if len(g) > 1), None)
            if factorable is None:
                continue

            prefix_length = _longest_common_prefix_length(factorable)
            prefix = factorable[0].rhs[:prefix_length]
            tail = _fresh_nonterminal(lhs, used_names)
            used_names.add(tail)
            new_nonterminals.append(tail)

            factored_id = f"{lhs}.factor{len(steps)}"
            productions = [p for p in productions if p not in factorable]
            productions.append(
                Production(
                    id=factored_id,
                    lhs=lhs,
                    rhs=(*prefix, tail),
                    description=f"left-factoring: common prefix of {[r.id for r in factorable]}",
                )
            )
            tail_ids: list[str] = []
            for rule in factorable:
                tail_id = f"{rule.id}.tail{len(steps)}"
                productions.append(
                    Production(
                        id=tail_id,
                        lhs=tail,
                        rhs=rule.rhs[prefix_length:],
                        evidence_statement_ids=rule.evidence_statement_ids,
                        description=f"left-factoring: remainder of {rule.id}",
                    )
                )
                tail_ids.append(tail_id)

            steps.append(
                TransformationStep(
                    kind=TransformationKind.LEFT_FACTORING,
                    description=(
                        f"Factored common prefix {prefix} on {lhs!r} using fresh "
                        f"nonterminal {tail!r}"
                    ),
                    source_production_ids=tuple(r.id for r in factorable),
                    result_production_ids=(factored_id, *tail_ids),
                )
            )
            changed = True
            break

    if not steps:
        return TransformResult(grammar=grammar, steps=())

    new_grammar = GrammarSpec(
        version=f"{grammar.version}+lf",
        start_symbol=grammar.start_symbol,
        terminals=grammar.terminals,
        nonterminals=(*grammar.nonterminals, *new_nonterminals),
        productions=tuple(productions),
    )
    return TransformResult(grammar=new_grammar, steps=tuple(steps))


def prepare_grammar(grammar: GrammarSpec) -> TransformResult:
    """Run left-recursion elimination followed by left-factoring, merging their ledgers."""
    after_recursion = eliminate_direct_left_recursion(grammar)
    after_factoring = left_factor(after_recursion.grammar)
    return TransformResult(
        grammar=after_factoring.grammar,
        steps=(*after_recursion.steps, *after_factoring.steps),
    )
