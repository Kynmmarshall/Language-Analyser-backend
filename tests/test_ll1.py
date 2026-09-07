"""Hand-computed FIRST/FOLLOW/SELECT/table tests using small symbolic teaching grammars."""

from __future__ import annotations

from yaounde_analyzer.core.grammar import compute_nullable
from yaounde_analyzer.core.ll1 import build_ll1_table, compute_first, compute_follow
from yaounde_analyzer.core.models import EOF, GrammarSpec, Production


def grammar(
    start: str, terminals: tuple[str, ...], nonterminals: tuple[str, ...], rules: list[tuple]
) -> GrammarSpec:
    productions = tuple(
        Production(id=f"p{i}", lhs=lhs, rhs=rhs) for i, (lhs, rhs) in enumerate(rules)
    )
    return GrammarSpec(
        version="test", start_symbol=start, terminals=terminals, nonterminals=nonterminals,
        productions=productions,
    )


def test_first_follow_and_table_for_the_optional_prefix_grammar() -> None:
    # S -> OPTIONAL NOUN ; OPTIONAL -> VERB | epsilon
    g = grammar("S", ("VERB", "NOUN"), ("S", "OPTIONAL"), [
        ("S", ("OPTIONAL", "NOUN")), ("OPTIONAL", ("VERB",)), ("OPTIONAL", ())])
    nullable = compute_nullable(g)
    assert nullable == {"OPTIONAL"}

    first = compute_first(g, nullable)
    assert first["OPTIONAL"] == {"VERB"}
    assert first["S"] == {"VERB", "NOUN"}

    follow = compute_follow(g, first, nullable)
    assert follow["S"] == {EOF}
    assert follow["OPTIONAL"] == {"NOUN"}

    table = build_ll1_table(g, first, follow, nullable)
    assert table.is_ll1
    s_rule, verb_rule, eps_rule = g.productions
    assert table.entries[("S", "VERB")] == s_rule.id
    assert table.entries[("S", "NOUN")] == s_rule.id
    assert table.entries[("OPTIONAL", "VERB")] == verb_rule.id
    assert table.entries[("OPTIONAL", "NOUN")] == eps_rule.id


def test_first_first_conflict_from_two_alternatives_sharing_a_first_symbol() -> None:
    g = grammar("A", ("VERB", "NOUN", "NUMBER"), ("A",), [
        ("A", ("VERB", "NOUN")), ("A", ("VERB", "NUMBER"))])
    nullable = compute_nullable(g)
    first = compute_first(g, nullable)
    follow = compute_follow(g, first, nullable)
    table = build_ll1_table(g, first, follow, nullable)

    assert not table.is_ll1
    assert len(table.conflicts) == 1
    conflict = table.conflicts[0]
    assert (conflict.nonterminal, conflict.terminal) == ("A", "VERB")
    assert set(conflict.production_ids) == {g.productions[0].id, g.productions[1].id}
    assert ("A", "VERB") not in table.entries


def test_first_follow_conflict_from_an_ambiguous_epsilon_alternative() -> None:
    # START -> OPTIONAL NOUN ; OPTIONAL -> NOUN | epsilon
    # FOLLOW(OPTIONAL) = {NOUN} clashes with FIRST(OPTIONAL -> NOUN) = {NOUN}.
    g = grammar("START", ("NOUN",), ("START", "OPTIONAL"), [
        ("START", ("OPTIONAL", "NOUN")), ("OPTIONAL", ("NOUN",)), ("OPTIONAL", ())])
    nullable = compute_nullable(g)
    first = compute_first(g, nullable)
    follow = compute_follow(g, first, nullable)
    table = build_ll1_table(g, first, follow, nullable)

    assert not table.is_ll1
    conflict = table.conflicts[0]
    assert (conflict.nonterminal, conflict.terminal) == ("OPTIONAL", "NOUN")
    assert set(conflict.production_ids) == {g.productions[1].id, g.productions[2].id}


def test_eof_propagates_through_a_nested_nullable_chain() -> None:
    # S -> A ; A -> epsilon : both S and A are nullable, and EOF must reach both FOLLOW sets.
    g = grammar("S", (), ("S", "A"), [("S", ("A",)), ("A", ())])
    nullable = compute_nullable(g)
    assert nullable == {"S", "A"}

    first = compute_first(g, nullable)
    assert first["S"] == set()
    assert first["A"] == set()

    follow = compute_follow(g, first, nullable)
    assert follow["S"] == {EOF}
    assert follow["A"] == {EOF}

    table = build_ll1_table(g, first, follow, nullable)
    assert table.is_ll1
    s_rule, a_rule = g.productions
    assert table.entries[("S", EOF)] == s_rule.id
    assert table.entries[("A", EOF)] == a_rule.id


def test_first_of_sequence_stops_at_the_first_non_nullable_symbol() -> None:
    from yaounde_analyzer.core.ll1 import first_of_sequence

    first = {"A": frozenset({"x"}), "B": frozenset({"y"}), "C": frozenset({"z"})}
    nullable = frozenset({"A"})
    # A is nullable so B's FIRST is included too, but B is not nullable so C is never reached.
    assert first_of_sequence(("A", "B", "C"), first, nullable) == {"x", "y"}
