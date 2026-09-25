# CS4110 Final Report

LaTeX sources for the Francanglais Studio report — a combined **Software Requirements
Specification** and **Software Design Document** covering the compiler-construction
coursework.

## Structure

| Part | Sections | Content |
| --- | --- | --- |
| I | 1 | Context, objective, scope, team |
| II | 2 | SRS — actors, FR/NFR tables, constraints, acceptance criteria |
| III | 3 | SDD — architecture, modules, data/interface/security design |
| IV | 4–8 | Data collection, lexical analysis, frequencies, grammar, parser |
| V | 9–11 | Results, linguistic discussion, conclusion |
| App. | A–D | Grammar reference, lexicon, screenshots, reproduction |

**Page budget.** The exam brief caps the report at 30 pages. The numbered body is kept at
≤ 31 pages; appendices carry the bulk evidence. Check after any edit:

```powershell
Select-String main.log -Pattern 'Output written'
Get-Content main.toc | Select-String 'section.A.'   # where the appendices start
```

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
| `main.tex` | Document root: front matter, part banners, section includes |
| `cover.tex` | Title page. The TikZ field height must clear all white text above the gold rule |
| `preamble.tex` | Packages, palette (mirrors `src/styles/theme.css`), callout boxes, helpers |
| `sections/` | Hand-written prose, one file per report section |
| `generated/` | **Auto-generated** tables and fact macros — do not edit |
| `diagrams/` | PlantUML sources |
| `figures/` | Rendered diagrams, screenshots and the app logo |
| `tools/` | The two generator scripts |

## Outstanding before submission

1. **Prepare the 10-minute slide deck and live demo.**
2. **Harden deployment** — replace the placeholder `YAOUNDE_SIGNUP_CODE` before the public
   instance is exposed.

## Editing rules

- Numbers in prose come from macros defined in `generated/facts.tex`
  (`\LexiconTotal`, `\CorpusAccepted`, `\LedgerSteps`, …). Use the macro, never a literal,
  so the report cannot drift from the code.
- Requirement ids use `\req{FR-1}` and are referenced from the SDD and the verification
  table in §9.3. Adding a requirement means updating both.
- Callout boxes: `keypoint` (green), `limitbox` (amber, honest limitations),
  `todobox` (red, outstanding team actions).
- Inline helpers: `\term{DET}` for terminals, `\nonterm{Clause}` for nonterminals,
  `\fw{taximan}` for Francanglais forms, `\accepted` / `\rejected` for verdicts.
