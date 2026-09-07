from __future__ import annotations

import argparse

from yaounde_analyzer import __version__
from yaounde_analyzer.core.scope import TARGET_VARIETY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yaounde-analyzer",
        description="Cameroonian Francanglais only. Lexer and parser are not implemented yet.",
    )
    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--scope", action="store_true", help="Print the fixed analysis target")
    args = parser.parse_args(argv)
    if args.scope:
        print(TARGET_VARIETY)
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
