# -*- coding: utf-8 -*-
"""
Generic context-free-grammar utilities: FIRST sets, FOLLOW sets, and LL(1)
parsing-table construction. Works on any grammar shaped like:

    {
      "start": "S",
      "productions": { "A": [["x","y"], ["EPS"]], ... }
    }

A symbol that is NOT a key in "productions" is treated as a terminal.
"EPS" is the epsilon (empty-string) symbol.
"""

EPS = "EPS"
END = "$"


def _is_terminal(symbol, productions):
    return symbol not in productions


def compute_first_sets(grammar):
    productions = grammar["productions"]
    first = {nt: set() for nt in productions}

    changed = True
    while changed:
        changed = False
        for nt, alternatives in productions.items():
            for prod in alternatives:
                # FIRST of the production body
                if prod == [EPS]:
                    if EPS not in first[nt]:
                        first[nt].add(EPS)
                        changed = True
                    continue
                add_eps = True
                for symbol in prod:
                    if _is_terminal(symbol, productions):
                        if symbol not in first[nt]:
                            first[nt].add(symbol)
                            changed = True
                        add_eps = False
                        break
                    else:
                        before = len(first[nt])
                        first[nt].update(first[symbol] - {EPS})
                        if len(first[nt]) != before:
                            changed = True
                        if EPS not in first[symbol]:
                            add_eps = False
                            break
                if add_eps:
                    if EPS not in first[nt]:
                        first[nt].add(EPS)
                        changed = True
    return first


def first_of_sequence(seq, first_sets, productions):
    """FIRST of a string of symbols (used for FOLLOW computation)."""
    result = set()
    if not seq:
        result.add(EPS)
        return result
    add_eps = True
    for symbol in seq:
        if _is_terminal(symbol, productions):
            result.add(symbol)
            add_eps = False
            break
        else:
            result.update(first_sets[symbol] - {EPS})
            if EPS not in first_sets[symbol]:
                add_eps = False
                break
    if add_eps:
        result.add(EPS)
    return result


def compute_follow_sets(grammar, first_sets):
    productions = grammar["productions"]
    start = grammar["start"]
    follow = {nt: set() for nt in productions}
    follow[start].add(END)

    changed = True
    while changed:
        changed = False
        for nt, alternatives in productions.items():
            for prod in alternatives:
                if prod == [EPS]:
                    continue
                for i, symbol in enumerate(prod):
                    if _is_terminal(symbol, productions):
                        continue
                    beta = prod[i + 1:]
                    first_beta = first_of_sequence(beta, first_sets, productions)
                    before = len(follow[symbol])
                    follow[symbol].update(first_beta - {EPS})
                    if EPS in first_beta or not beta:
                        follow[symbol].update(follow[nt])
                    if len(follow[symbol]) != before:
                        changed = True
    return follow


def build_ll1_table(grammar, first_sets, follow_sets):
    productions = grammar["productions"]
    table = {}  # table[nonterminal][terminal] = production (list of symbols)
    conflicts = []

    for nt, alternatives in productions.items():
        table[nt] = {}
        for prod in alternatives:
            first_prod = first_of_sequence(
                prod if prod != [EPS] else [], first_sets, productions
            )
            for terminal in first_prod - {EPS}:
                if terminal in table[nt]:
                    conflicts.append({"nonterminal": nt, "terminal": terminal})
                table[nt][terminal] = prod
            if EPS in first_prod or prod == [EPS]:
                for terminal in follow_sets[nt]:
                    if terminal in table[nt] and table[nt][terminal] != prod:
                        conflicts.append({"nonterminal": nt, "terminal": terminal})
                    table[nt][terminal] = prod
    return table, conflicts


def analyze_grammar(grammar):
    first_sets = compute_first_sets(grammar)
    follow_sets = compute_follow_sets(grammar, first_sets)
    table, conflicts = build_ll1_table(grammar, first_sets, follow_sets)
    return {
        "first": {k: sorted(v) for k, v in first_sets.items()},
        "follow": {k: sorted(v) for k, v in follow_sets.items()},
        "table": {
            nt: {term: prod for term, prod in row.items()}
            for nt, row in table.items()
        },
        "conflicts": conflicts,
        "is_ll1": len(conflicts) == 0,
    }


# ---------------------------------------------------------------------------
# POS-tagging: map lexer word-categories to grammar terminal symbols
# ---------------------------------------------------------------------------

DET_WORDS = {"the", "this", "that", "dis", "dat", "some", "a", "le", "la", "les"}
PRON_WORDS = {"me", "you", "i", "we", "dem", "na", "on", "quoi", "qui"}
PREP_WORDS = {"for", "to", "from", "with", "since"}
CONJ_WORDS = {"and", "but", "or", "then", "ou", "mais"}


def token_to_terminal(token, category):
    """
    Maps one lexer token (word + its lexical category) to a grammar
    terminal (DET / NOUN / PRON / VERB / PREP / CONJ). Returns None when the
    token has no place in the sentence grammar (e.g. bare SLANG, PUNCT,
    NUMBER, or unresolved CODEMIX) — such tokens are skipped by the parser's
    POS-tagging step and, if essential, will make the sentence be REJECTED.
    """
    w = token.lower()
    if w in DET_WORDS:
        return "DET"
    if w in PRON_WORDS:
        return "PRON"
    if w in PREP_WORDS:
        return "PREP"
    if w in CONJ_WORDS:
        return "CONJ"
    if category == "NOUN":
        return "NOUN"
    if category == "VERB":
        return "VERB"
    return None


def tag_sentence(tokens):
    """
    tokens: list of {token, category} from lexer.tokenize().
    Returns (terminals, skipped) where terminals is the list of grammar
    terminals fed to the parser, and skipped lists tokens with no terminal.
    """
    terminals = []
    skipped = []
    for t in tokens:
        term = token_to_terminal(t["token"], t["category"])
        if term:
            terminals.append(term)
        else:
            skipped.append(t)
    return terminals, skipped
