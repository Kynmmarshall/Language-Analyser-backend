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

### Exporting from the live corpus instead of the packaged copy

By default `export_tables.py` reads the field corpus bundled with the package
(`src/yaounde_analyzer/specs/demo/corpus.json`) — 22 attested statements attributed across
the three team members. Point it at a running database to publish whatever that instance
holds instead:

```powershell
& "..\..\.venv\Scripts\python.exe" tools\export_tables.py `
    --database "sqlite:///../../data/app.db" --field-only
```

`--field-only` keeps just the manually attested `field` records, which is what the marking
scheme counts. Without it, any `demo` fixtures are included and flagged in the results
table.

### Screenshots

Appendix C's figures are captured from the running application by a script in the
**front-end** repository. With the dev server on 5175 and the API reachable:

```powershell
cd "..\..\..\Language Analyser"
$env:REPORT_BASE_URL="http://localhost:5175"
$env:REPORT_USER="<collector>"; $env:REPORT_PASS="<password>"
node scripts/capture-report-screenshots.mjs
```

It writes the eight `shot-*.png` files straight into `figures/`. Any missing file renders
as a visible "Screenshot pending" placeholder rather than breaking the build.

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

1. **Prepare the 10-minute slide deck and live demo.**
2. **Harden deployment** — replace the placeholder `YAOUNDE_SIGNUP_CODE` before the public
   instance is exposed.

## Editing rules

- Numbers in prose come from macros defined in `generated/facts.tex`
  (`\LexiconTotal`, `\CorpusAccepted`, `\LedgerSteps`, …). Use the macro, never a literal,
  so the report cannot drift from the code.
- Callout boxes: `keypoint` (navy), `limitbox` (orange, honest limitations),
  `todobox` (red, outstanding team actions).
- Inline helpers: `\term{DET}` for terminals, `\nonterm{Clause}` for nonterminals,
  `\fw{taximan}` for Francanglais forms, `\accepted` / `\rejected` for verdicts.
