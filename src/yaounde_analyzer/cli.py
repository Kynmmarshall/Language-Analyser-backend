"""Command-line entry point: scope info plus analyze / grammar-check / corpus-validate.

The API layer, authentication, and deployment are not implemented yet; this CLI is the
first usable surface for the compiler core built in Phase 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from yaounde_analyzer import __version__
from yaounde_analyzer.core.analysis import (
    PreparedAnalyzer,
    analyze_corpus,
    analyze_tokens_and_parse,
    compute_statistics,
)
from yaounde_analyzer.core.corpus import CorpusImportError, validate_import
from yaounde_analyzer.core.parser import ParserConfigurationError
from yaounde_analyzer.core.scope import TARGET_VARIETY
from yaounde_analyzer.core.specs import load_demo_grammar, load_demo_lexicon


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yaounde-analyzer",
        description="Cameroonian Francanglais only. Uses the bundled demo lexicon/grammar.",
    )
    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--scope", action="store_true", help="Print the fixed analysis target")
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Tokenize and parse one statement")
    analyze_parser.add_argument("text", help="The statement text to analyze")
    analyze_parser.add_argument("--json", action="store_true", help="Print full JSON output")

    grammar_parser = subparsers.add_parser(
        "grammar-check", help="Report whether the demo grammar is valid LL(1)"
    )
    grammar_parser.add_argument(
        "--show-steps", action="store_true", help="List the transformation ledger"
    )

    corpus_parser = subparsers.add_parser(
        "corpus-validate", help="Validate a JSON corpus file (and optionally analyze it)"
    )
    corpus_parser.add_argument("path", type=Path, help="Path to a JSON array of statement records")
    corpus_parser.add_argument(
        "--analyze", action="store_true", help="Also analyze each statement and report stats"
    )

    return parser


def _cmd_analyze(text: str, as_json: bool) -> int:
    analyzer = PreparedAnalyzer(load_demo_lexicon(), load_demo_grammar())
    tokens, parse, topics = analyze_tokens_and_parse(text, analyzer)
    if as_json:
        payload = {
            "tokens": [t.model_dump(mode="json") for t in tokens],
            "parse": parse.model_dump(mode="json"),
            "topics": [t.model_dump(mode="json") for t in topics],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"Tokens ({len(tokens)}):")
    for token in tokens:
        print(f"  {token.raw!r:<20} canonical={token.canonical!r:<20} terminal={token.terminal}")
    if parse.accepted:
        print(f"\nACCEPTED ({parse.matched_token_count} tokens matched)")
    else:
        print(f"\nREJECTED: {parse.rejection_reason}")
        if parse.expected_terminals:
            print(f"  expected one of: {', '.join(parse.expected_terminals)}")
        if parse.failing_position is not None:
            print(f"  at position: {parse.failing_position}")
    if topics:
        print("\nTopics:")
        for topic in topics:
            print(f"  {topic.topic}: {', '.join(topic.matched_terms)}")
    return 0


def _cmd_grammar_check(show_steps: bool) -> int:
    analyzer = PreparedAnalyzer(load_demo_lexicon(), load_demo_grammar())
    if analyzer.table.is_ll1:
        print(f"Grammar {analyzer.descriptive_grammar.version!r} is valid LL(1).")
    else:
        print(f"Grammar {analyzer.descriptive_grammar.version!r} has conflicts:")
        for conflict in analyzer.table.conflicts:
            print(f"  ({conflict.nonterminal}, {conflict.terminal}): {conflict.production_ids}")
    if show_steps:
        print(f"\nTransformation steps ({len(analyzer.transformation_steps)}):")
        for step in analyzer.transformation_steps:
            print(f"  [{step.kind}] {step.description}")
    return 0 if analyzer.table.is_ll1 else 1


def _cmd_corpus_validate(path: Path, do_analyze: bool) -> int:
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
        revisions = validate_import(records)
    except (CorpusImportError, OSError, json.JSONDecodeError) as error:
        print(f"Corpus validation failed: {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(revisions)} statement revision(s).")
    if not do_analyze:
        return 0

    try:
        analyzer = PreparedAnalyzer(load_demo_lexicon(), load_demo_grammar())
        results = analyze_corpus(revisions, analyzer)
    except ParserConfigurationError as error:
        print(f"Grammar is not usable: {error}", file=sys.stderr)
        return 1

    stats = compute_statistics(results)
    print(f"Accepted: {stats.accepted_count}  Rejected: {stats.rejected_count}")
    if stats.unknown_words:
        print(f"Unknown words: {', '.join(stats.unknown_words)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return _cmd_analyze(args.text, args.json)
    if args.command == "grammar-check":
        return _cmd_grammar_check(args.show_steps)
    if args.command == "corpus-validate":
        return _cmd_corpus_validate(args.path, args.analyze)
    if args.scope:
        print(TARGET_VARIETY)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
