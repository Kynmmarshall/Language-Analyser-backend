"""Loads bundled JSON specs (lexicon, grammar, demo corpus) into validated contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from yaounde_analyzer.core.lexicon import LexiconSpec
from yaounde_analyzer.core.models import GrammarSpec

_SPECS_DIR: Final = Path(__file__).resolve().parent.parent / "specs"

# Bundled with the package rather than left at the repo root so it is present in the
# installed wheel, and therefore inside the container image.
DEMO_CORPUS_PATH: Final = _SPECS_DIR / "demo" / "corpus.json"


def load_lexicon_spec(path: Path) -> LexiconSpec:
    return LexiconSpec.model_validate_json(path.read_text(encoding="utf-8"))


def load_grammar_spec(path: Path) -> GrammarSpec:
    return GrammarSpec.model_validate_json(path.read_text(encoding="utf-8"))


def load_demo_lexicon() -> LexiconSpec:
    return load_lexicon_spec(_SPECS_DIR / "demo" / "lexicon.json")


def load_demo_grammar() -> GrammarSpec:
    return load_grammar_spec(_SPECS_DIR / "demo" / "grammar.json")


def load_demo_corpus_records() -> list[dict[str, Any]]:
    """The raw demo statement records, still unvalidated so importers see the same input."""
    return json.loads(DEMO_CORPUS_PATH.read_text(encoding="utf-8"))


__all__ = [
    "DEMO_CORPUS_PATH",
    "load_demo_corpus_records",
    "load_demo_grammar",
    "load_demo_lexicon",
    "load_grammar_spec",
    "load_lexicon_spec",
]
