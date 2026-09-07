"""Hand-computed tests for nullable analysis, cycle detection, and grammar transformations.

These use small symbolic grammars (S, A, E, T, ...) chosen so every expected set, cycle,
and transformation result can be verified by hand — they are teaching fixtures, not
statements from the Francanglais corpus.
"""

from __future__ import annotations

import pytest

from yaounde_analyzer.core.grammar import (
    GrammarTransformError,
    compute_nullable,
    eliminate_direct_left_recursion,
    find_left_recursive_cycles,
    find_unproductive_nonterminals,
    find_unreachable_nonterminals,
    left_factor,
)
from yaounde_analyzer.core.models import GrammarSpec, Production


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


def test_nullable_propagates_through_a_chain() -> None:
    # S -> A B ; A -> epsilon ; B -> epsilon  =>  A, B, and S (transitively) are nullable.
    g = grammar("S", ("x",), ("S", "A", "B"), [
        ("S", ("A", "B")), ("A", ()), ("B", ())])
    assert compute_nullable(g) == {"S", "A", "B"}


def test_nullable_excludes_nonterminals_requiring_a_terminal() -> None:
    g = grammar("S", ("x",), ("S", "A"), [("S", ("A",)), ("A", ("x",))])
    assert compute_nullable(g) == set()


def test_unreachable_nonterminal_is_detected() -> None:
    g = grammar("S", ("x", "y"), ("S", "A", "Dead"), [
        ("S", ("A",)), ("A", ("x",)), ("Dead", ("y",))])
    assert find_unreachable_nonterminals(g) == {"Dead"}


def test_unproductive_nonterminal_is_detected() -> None:
    # Loop is only ever referenced by itself, so it can never derive a terminal string.
    g = grammar("S", ("x",), ("S", "Loop"), [("S", ("x",)), ("Loop", ("Loop",))])
    assert find_unproductive_nonterminals(g) == {"Loop"}


def test_no_cycles_in_a_non_recursive_grammar() -> None:
    g = grammar("S", ("x", "y"), ("S", "A"), [("S", ("A", "y")), ("A", ("x",))])
    assert find_left_recursive_cycles(g) == ()


def test_direct_left_recursion_is_detected_as_a_single_element_cycle() -> None:
    g = grammar("A", ("x", "y"), ("A",), [("A", ("A", "x")), ("A", ("y",))])
    assert find_left_recursive_cycles(g) == (("A",),)


def test_indirect_left_recursion_is_detected_across_two_nonterminals() -> None:
    g = grammar("A", ("x", "y"), ("A", "B"), [
        ("A", ("B", "x")), ("B", ("A", "y")), ("B", ("x",))])
    cycles = find_left_recursive_cycles(g)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}


def test_left_recursion_hidden_behind_a_nullable_prefix_is_detected() -> None:
    # A -> C A "x" with C nullable means A's effective left corner includes A itself.
    g = grammar("A", ("x",), ("A", "C"), [("A", ("C", "A", "x")), ("A", ("x",)), ("C", ())])
    assert find_left_recursive_cycles(g) == (("A",),)


def test_eliminate_direct_left_recursion_produces_the_textbook_shape() -> None:
    # Classic E -> E + T | T ; T -> id
    g = grammar("E", ("+", "id"), ("E", "T"), [
        ("E", ("E", "+", "T")), ("E", ("T",)), ("T", ("id",))])
    result = eliminate_direct_left_recursion(g)
    new_grammar = result.grammar
    assert len(result.steps) == 1

    tail = next(nt for nt in new_grammar.nonterminals if nt not in g.nonterminals)
    rules_by_lhs: dict[str, list[tuple]] = {}
    for p in new_grammar.productions:
        rules_by_lhs.setdefault(p.lhs, []).append(p.rhs)

    assert set(rules_by_lhs["E"]) == {("T", tail)}
    assert set(rules_by_lhs[tail]) == {("+", "T", tail), ()}
    assert rules_by_lhs["T"] == [("id",)]


def test_eliminate_direct_left_recursion_is_a_no_op_without_recursion() -> None:
    g = grammar("S", ("x",), ("S",), [("S", ("x",))])
    result = eliminate_direct_left_recursion(g)
    assert result.steps == ()
    assert result.grammar == g


def test_eliminate_direct_left_recursion_rejects_purely_recursive_nonterminal() -> None:
    g = grammar("A", ("x",), ("A",), [("A", ("A", "x"))])
    with pytest.raises(GrammarTransformError, match="no non-recursive alternative"):
        eliminate_direct_left_recursion(g)


def test_eliminate_direct_left_recursion_rejects_indirect_recursion() -> None:
    g = grammar("A", ("x", "y"), ("A", "B"), [
        ("A", ("B", "x")), ("B", ("A", "y")), ("B", ("x",))])
    with pytest.raises(GrammarTransformError, match="indirect left recursion"):
        eliminate_direct_left_recursion(g)


def test_left_factor_splits_a_simple_shared_prefix() -> None:
    g = grammar("A", ("if", "x", "y", "z"), ("A",), [
        ("A", ("if", "x")), ("A", ("if", "y")), ("A", ("z",))])
    result = left_factor(g)
    assert len(result.steps) == 1

    rules_by_lhs: dict[str, list[tuple]] = {}
    for p in result.grammar.productions:
        rules_by_lhs.setdefault(p.lhs, []).append(p.rhs)
    tail = next(nt for nt in result.grammar.nonterminals if nt not in g.nonterminals)

    assert set(rules_by_lhs["A"]) == {("if", tail), ("z",)}
    assert set(rules_by_lhs[tail]) == {("x",), ("y",)}


def test_left_factor_runs_to_a_fixed_point_across_two_passes() -> None:
    # A -> a b c | a b d | a e : one common prefix "a" reveals a second, "b", underneath.
    g = grammar("A", ("a", "b", "c", "d", "e"), ("A",), [
        ("A", ("a", "b", "c")), ("A", ("a", "b", "d")), ("A", ("a", "e"))])
    result = left_factor(g)
    assert len(result.steps) == 2

    rules_by_lhs: dict[str, list[tuple]] = {}
    for p in result.grammar.productions:
        rules_by_lhs.setdefault(p.lhs, []).append(p.rhs)
    first_tail = next(nt for nt in result.grammar.nonterminals if nt not in g.nonterminals)
    second_tail = next(
        nt for nt in result.grammar.nonterminals
        if nt not in g.nonterminals and nt != first_tail
    )

    assert set(rules_by_lhs["A"]) == {("a", first_tail)}
    assert set(rules_by_lhs[first_tail]) == {("b", second_tail), ("e",)}
    assert set(rules_by_lhs[second_tail]) == {("c",), ("d",)}


def test_left_factor_is_a_no_op_without_shared_prefixes() -> None:
    g = grammar("A", ("x", "y"), ("A",), [("A", ("x",)), ("A", ("y",))])
    result = left_factor(g)
    assert result.steps == ()
    assert result.grammar == g
