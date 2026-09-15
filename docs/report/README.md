# CS4110 Final Report

LaTeX sources for the Francanglais Studio compiler-construction report.

## Build

```powershell
# from this directory
pwsh ./build.ps1
```

This runs three steps in order:

1. `tools/export_tables.py` — re-exports every data table in `generated/` **directly from
   the live analyzer**. Nothing in `generated/` is hand-written; edits there are lost.
2. `tools/render_diagrams.py` — renders `diagrams/*.puml` to `figures/*.png` via the
   public PlantUML server (needs network access).
3. `latexmk -pdf main.tex` — compiles `main.pdf`.

Useful flags:

```powershell
./build.ps1 -SkipDiagrams   # offline; reuse existing figures/*.png
./build.ps1 -SkipTables     # prose-only changes
```

Or manually:

```powershell
& "..\..\.venv\Scripts\python.exe" tools\export_tables.py
& "..\..\.venv\Scripts\python.exe" tools\render_diagrams.py
latexmk -pdf -interaction=nonstopmode main.tex
```

## Layout

| Path | Contents |
| --- | --- |
| `main.tex` | Document root: title page, TOC, section includes |
| `preamble.tex` | Packages, palette, section styling, callout boxes, helper macros |
| `sections/` | Hand-written prose, one file per report section |
| `generated/` | **Auto-generated** tables and fact macros — do not edit |
| `diagrams/` | PlantUML sources |
| `figures/` | Rendered diagrams and screenshots |
| `tools/` | The two generator scripts |

## Outstanding before submission

1. **Collect the field corpus.** 10–15 real statements, manually transcribed, entered with
   `source_kind = field` and the attestation ticked. Then re-run `export_tables.py`; the
   data tables repopulate automatically and no prose needs rewriting.
2. **Add screenshots.** Drop PNGs into `figures/` using the filenames listed in
   Appendix C (`shot-analyser.png`, `shot-tokens.png`, …). Missing files render as a
   visible "Screenshot pending" placeholder, so it is obvious what is still outstanding.
3. **Prepare the 10-minute slide deck and live demo.**

## Editing rules

- Numbers in prose come from macros defined in `generated/facts.tex`
  (`\LexiconTotal`, `\CorpusAccepted`, `\LedgerSteps`, …). Use the macro, never a literal,
  so the report cannot drift from the code.
- Callout boxes: `keypoint` (navy), `limitbox` (orange, honest limitations),
  `todobox` (red, outstanding team actions).
- Inline helpers: `\term{DET}` for terminals, `\nonterm{Clause}` for nonterminals,
  `\fw{taximan}` for Francanglais forms, `\accepted` / `\rejected` for verdicts.
