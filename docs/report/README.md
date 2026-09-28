# CS4110 Final Report

Two PDFs are built from one source tree. They share `preamble.tex`, `cover.tex`,
`generated/` and `figures/`, so **data tables can never diverge between them** — only the
prose files differ.

| Document | Pages | Purpose |
| --- | --- | --- |
| `main-compact.pdf` | **30** | **Submit this.** Meets the brief's "should not exceed 30 pages". |
| `main.pdf` | 53 | Full reference: same content plus expanded SRS/SDD and four appendices. |

```powershell
pwsh ./build.ps1        # exports tables, renders diagrams, builds BOTH PDFs
```

## Structure

`main-compact.tex` → `sections-compact/` (12 sections, no appendices):

| § | Content | Covers |
| --- | --- | --- |
| 1 | Introduction, team + matricules | — |
| 2 | Requirements (actors, use-case diagram, FR/NFR) | — |
| 3 | System design (architecture, pipeline, sequence, data, security) | — |
| 4 | Data collection | Component 1 |
| 5 | Lexical analysis, regexes, token categories | Component 2.1–2.2 |
| 6 | Token frequency and variation | Component 2.3 |
| 7 | Grammar, left recursion, left factoring, FIRST/FOLLOW, LL(1) table | Component 3.1–3.2 |
| 8 | Parser, worked trace, error reporting | Component 4 |
| 9 | Raw statements + accept/reject verdicts, verification | Component 3.3–3.4 |
| 10 | Screenshots of the working analyzer | Deliverable A.vi |
| 11 | Why Yaoundé communication is linguistically complex | Deliverable A.vii |
| 12 | Conclusion, limitations, reproduction | — |

`main.tex` → `sections/` (Parts I–V + Appendices A–D).

**Page budget.** `main-compact.pdf` is at exactly 30 physical pages (cover + 29 numbered).
Re-check after any edit:

```powershell
Select-String main-compact.log -Pattern 'Output written'
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
| `main.tex` / `main-compact.tex` | The two document roots |
| `cover.tex` | Shared title page. The TikZ field height must clear all white text above the gold rule, and the keyline must end above it |
| `preamble.tex` | Packages, palette (mirrors `src/styles/theme.css`), callout boxes, helpers |
| `sections/` | Prose for the full report |
| `sections-compact/` | Prose for the 30-page submission |
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
  so the reports cannot drift from the code.
- Prose changes affecting both documents must be made in `sections/` **and**
  `sections-compact/`. Data tables are shared, so those never need duplicating.
- Requirement ids use `\req{FR-1}` and are referenced from the design section and the
  verification table. Adding a requirement means updating both.
- Callout boxes: `keypoint` (green), `limitbox` (amber, honest limitations),
  `todobox` (red, outstanding team actions).
- Inline helpers: `\term{DET}` for terminals, `\nonterm{Clause}` for nonterminals,
  `\fw{taximan}` for Francanglais forms, `\accepted` / `\rejected` for verdicts.
