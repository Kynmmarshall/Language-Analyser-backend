"""Public grammar/lexicon inspection: the compiler's own spec, not private corpus data."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from yaounde_analyzer.api.deps import get_analyzer
from yaounde_analyzer.api.schemas import GrammarView, SymbolSet, TableConflictView, TableEntry
from yaounde_analyzer.core.analysis import PreparedAnalyzer

router = APIRouter(prefix="/api", tags=["grammar"])


@router.get("/grammar", response_model=GrammarView)
def get_grammar(analyzer: PreparedAnalyzer = Depends(get_analyzer)) -> GrammarView:
    return GrammarView(
        lexicon=analyzer.lexicon.entries,
        descriptive_grammar=analyzer.descriptive_grammar,
        grammar=analyzer.grammar,
        transformation_steps=analyzer.transformation_steps,
        nullable=tuple(sorted(analyzer.nullable)),
        first=tuple(
            SymbolSet(symbol=symbol, terminals=tuple(sorted(terminals)))
            for symbol, terminals in sorted(analyzer.first.items())
        ),
        follow=tuple(
            SymbolSet(symbol=symbol, terminals=tuple(sorted(terminals)))
            for symbol, terminals in sorted(analyzer.follow.items())
        ),
        table_entries=tuple(
            TableEntry(nonterminal=nonterminal, terminal=terminal, production_id=production_id)
            for (nonterminal, terminal), production_id in sorted(analyzer.table.entries.items())
        ),
        table_conflicts=tuple(
            TableConflictView(
                nonterminal=conflict.nonterminal,
                terminal=conflict.terminal,
                production_ids=conflict.production_ids,
            )
            for conflict in analyzer.table.conflicts
        ),
    )
