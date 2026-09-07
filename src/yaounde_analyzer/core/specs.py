"""Loads bundled JSON specs (lexicon, grammar) into their validated Pydantic contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from yaounde_analyzer.core.lexicon import LexiconSpec
from yaounde_analyzer.core.models import GrammarSpec

_SPECS_DIR: Final = Path(__file__).resolve().parent.parent / "specs"


def load_lexicon_spec(path: Path) -> LexiconSpec:
    return LexiconSpec.model_validate_json(path.read_text(encoding="utf-8"))


def load_grammar_spec(path: Path) -> GrammarSpec:
    return GrammarSpec.model_validate_json(path.read_text(encoding="utf-8"))


def load_demo_lexicon() -> LexiconSpec:
    return load_lexicon_spec(_SPECS_DIR / "demo" / "lexicon.json")


def load_demo_grammar() -> GrammarSpec:
    return load_grammar_spec(_SPECS_DIR / "demo" / "grammar.json")


__all__ = ["load_demo_grammar", "load_demo_lexicon", "load_grammar_spec", "load_lexicon_spec"]
