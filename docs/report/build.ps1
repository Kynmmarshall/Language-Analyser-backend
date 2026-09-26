<#
.SYNOPSIS
    Builds the CS4110 final report end to end.

.DESCRIPTION
    1. Re-exports every data table from the live analyzer.
    2. Re-renders the PlantUML diagrams (requires network access).
    3. Compiles main.tex with latexmk.

.PARAMETER SkipDiagrams
    Skip diagram rendering (useful offline; existing figures/*.png are reused).

.PARAMETER SkipTables
    Skip table export (useful when only prose changed).
#>
[CmdletBinding()]
param(
    [switch]$SkipDiagrams,
    [switch]$SkipTables
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$python = Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }

if (-not $SkipTables) {
    Write-Host '==> Exporting data tables from the analyzer' -ForegroundColor Cyan
    & $python 'tools/export_tables.py'
    if ($LASTEXITCODE -ne 0) { throw 'export_tables.py failed' }
}

if (-not $SkipDiagrams) {
    Write-Host '==> Rendering PlantUML diagrams' -ForegroundColor Cyan
    & $python 'tools/render_diagrams.py'
    if ($LASTEXITCODE -ne 0) { throw 'render_diagrams.py failed' }
}

foreach ($doc in @('main', 'main-compact')) {
    Write-Host "==> Compiling $doc.tex" -ForegroundColor Cyan
    & latexmk -pdf -interaction=nonstopmode -halt-on-error "$doc.tex"
    if ($LASTEXITCODE -ne 0) { throw "latexmk failed on $doc.tex" }
}

Write-Host ''
foreach ($doc in @('main', 'main-compact')) {
    $pages = (Select-String -Path "$doc.log" -Pattern 'Output written on .*\((\d+) pages' |
              Select-Object -Last 1).Matches.Groups[1].Value
    $label = if ($doc -eq 'main') { 'full reference' } else { 'submission, 30-page cap' }
    Write-Host ("Built {0}.pdf  {1,3} pages  ({2})" -f $doc, $pages, $label) -ForegroundColor Green
}
