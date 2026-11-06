# LegalWriting Toolkit Windows bootstrap — Preview by default
# Requires Windows Package Manager. Use -Apply to opt in, package by package.
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
Write-Host 'LegalWriting Windows Toolchain (safe preview by default)'
$programs = @(
    @{ Name = 'Git'; Id = 'Git.Git' },
    @{ Name = 'Pandoc'; Id = 'JohnMacFarlane.Pandoc' },
    @{ Name = 'LibreOffice'; Id = 'TheDocumentFoundation.LibreOffice' },
    @{ Name = 'Python 3.12'; Id = 'Python.Python.3.12' },
    @{ Name = 'Graphviz'; Id = 'Graphviz.Graphviz' },
    @{ Name = 'Zotero'; Id = 'DigitalScholar.Zotero' }
)
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw 'winget not found. Install App Installer from a trusted Microsoft source or ask IT.'
}
foreach ($app in $programs) {
    Write-Host "`n>>> $($app.Name) ($($app.Id))"
    Write-Host "PREVIEW: winget search --id $($app.Id); winget show --id $($app.Id)"
    if ($Apply) {
        & winget show --id $app.Id --source winget
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Package ID not found; skipped'; continue }
        $yes = Read-Host 'Install this package? type YES (anything else skips)'
        if ($yes -ceq 'YES') {
            & winget install --id $app.Id --exact --source winget
            if ($LASTEXITCODE -ne 0) { Write-Warning 'Install failed; check winget logs' }
        } else { Write-Host 'Skipped' }
    }
}
Write-Host "`nFonts are NOT installed automatically. Read docs/02_한글폰트_근거_추천_설치.md"
Write-Host 'Python packages are installed in a separate .venv from requirements.txt'
Write-Host 'No security policy changes were performed.'
