"""Command-line entry point.

Lexer, grammar, and parser subcommands are added as those modules are implemented.
"""

from __future__ import annotations

import sys

from yaounde_analyzer import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in {"--version", "-V"}:
        print(f"yaounde-analyzer {__version__}")
        return 0
    print(f"yaounde-analyzer {__version__}: no subcommands are implemented yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
