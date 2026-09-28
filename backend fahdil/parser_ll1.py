# -*- coding: utf-8 -*-
"""
LL(1) predictive parser. Given an LL(1) table (built by grammar_utils) and a
list of input terminals, simulates the standard stack-based algorithm and
returns a step-by-step trace plus an accept/reject verdict.

Each trace row (and the top-level error, if any) carries BOTH a ready-made
English `action`/`error` string (kept for anyone consuming this API directly,
e.g. from a script or curl) AND a structured `action_type` + `action_params`
(`error_type` + `error_params` at the top level) — the frontend uses the
structured form to render the same information in French or English without
the backend needing to know which language the UI is currently showing.
"""

EPS = "EPS"
END = "$"


def parse(grammar, table, terminals):
    start = grammar["start"]
    stack = [END, start]
    input_symbols = list(terminals) + [END]
    pos = 0
    trace = []
    accepted = False
    error = None
    error_type = None
    error_params = None

    max_steps = 500
    steps = 0
    while stack and steps < max_steps:
        steps += 1
        top = stack[-1]
        current = input_symbols[pos] if pos < len(input_symbols) else END

        row = {
            "stack": " ".join(reversed(stack)),
            "remaining_input": " ".join(input_symbols[pos:]),
        }

        if top == END and current == END:
            row["action"] = "ACCEPT"
            row["action_type"] = "accept"
            row["action_params"] = {}
            trace.append(row)
            accepted = True
            break

        if top not in grammar["productions"]:
            # top is a terminal (or END) — must match current input symbol
            if top == current:
                row["action"] = "MATCH {}".format(top)
                row["action_type"] = "match"
                row["action_params"] = {"terminal": top}
                trace.append(row)
                stack.pop()
                pos += 1
                continue
            else:
                row["action"] = "ERROR: expected '{}' but found '{}'".format(top, current)
                row["action_type"] = "error_expected"
                row["action_params"] = {"expected": top, "found": current}
                trace.append(row)
                error = row["action"]
                error_type = row["action_type"]
                error_params = row["action_params"]
                break

        # top is a non-terminal: consult the LL(1) table
        production = table.get(top, {}).get(current)
        if production is None:
            row["action"] = (
                "ERROR: no rule for {} on input '{}' "
                "(sentence does not fit the grammar)".format(top, current)
            )
            row["action_type"] = "error_no_rule"
            row["action_params"] = {"nonterminal": top, "terminal": current}
            trace.append(row)
            error = row["action"]
            error_type = row["action_type"]
            error_params = row["action_params"]
            break

        row["action"] = "{} -> {}".format(top, " ".join(production))
        row["action_type"] = "expand"
        row["action_params"] = {"nonterminal": top, "production": list(production)}
        trace.append(row)
        stack.pop()
        if production != [EPS]:
            for symbol in reversed(production):
                stack.append(symbol)

    return {
        "accepted": accepted,
        "error": error,
        "error_type": error_type,
        "error_params": error_params,
        "trace": trace,
    }
