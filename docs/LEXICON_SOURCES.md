# Lexicon Sources And Attribution

The lexicon in `src/yaounde_analyzer/specs/demo/lexicon.json` has entries from two
different kinds of evidence. Every entry records which, in its `source` field, so a
reader can always tell them apart.

## `source: "corpus"`

The entry exists because a reviewed statement in the corpus uses the word. These
entries must cite at least one `evidence_statement_ids` value; `LexiconSpec`
rejects the spec if a `corpus` entry cites nothing. This is the stronger claim:
the word was observed in use, and the statement that attests it can be read back.

## `source: "dictionary"`

The entry comes from a published reference work rather than from our own corpus.
These entries carry no `evidence_statement_ids`. They widen lexical coverage so the
lexer recognises more real input, but they are **not** evidence that a word was
observed in the field, and they should not be reported as field findings.

### Reference used

- *Annexe:Camfranglais*, French Wiktionary.
  <https://fr.wiktionary.org/wiki/Annexe:Camfranglais>
  Licensed CC BY-SA 4.0 (<https://creativecommons.org/licenses/by-sa/4.0/>).

A second group of `dictionary` entries is not from that annex: the common French
closed-class words (determiners, pronouns, prepositions, conjunctions, auxiliaries)
that Francanglais is built on. They carry no citation because they are ordinary
standard French, and they exist so that everyday input reaches the parser instead of
failing as unknown vocabulary.

Glosses in the `description` field are written fresh in English rather than copied
from the source text. Origin labels in `language_candidates` follow the source's
etymological notes where it gives them, and fall back to `uncertain` where it does
not; several are contested and should be treated as candidates, not conclusions.

## Known limitations

- The reference is community-edited and uneven in quality. Spellings vary widely in
  Camfranglais, and the form recorded here is one attested variant, not a standard.
- The entries have not been reviewed by a native speaker. Before these are relied on
  for any claim about usage, a speaker should check the glosses and origin labels.
- Adding or changing any entry changes the export bundle's `spec_hash`, so analyses
  run before and after a lexicon change are not directly comparable.
