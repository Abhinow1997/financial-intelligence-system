# Lab 7 setup for Windows (PowerShell 5.1+). Installs the GitHub CLI and the gh-aw
# extension, then checks the repository. It never asks for, stores or prints a token.
#
#   powershell -ExecutionPolicy Bypass -File gh-aw-lab\scripts\setup-windows.ps1
#
# Native commands (gh, winget) report failure through $LASTEXITCODE. We check it
# explicitly instead of using $ErrorActionPreference = "Stop": in Windows PowerShell 5.1,
# "Stop" turns anything gh prints on stderr (including normal "not signed in"
# messages) into a crash.

$GhAwVersion = "v1.2.2"   # the version this lab was written against

function Find-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $default = "C:\Program Files\GitHub CLI\gh.exe"
    if (Test-Path $default) { return $default }
    return $null
}

Write-Host "== 1/4 GitHub CLI" -ForegroundColor Cyan
$gh = Find-Gh
if (-not $gh) {
    Write-Host "Installing GitHub CLI with winget..."
    winget install --id GitHub.cli -e --silent --accept-source-agreements --accept-package-agreements
    $gh = Find-Gh
    if (-not $gh) {
        Write-Host "gh not found after install. Open a new terminal and re-run this script." -ForegroundColor Red
        exit 1
    }
}
& $gh --version | Select-Object -First 1

# Signing in comes before the extension step: `gh extension list` needs an account.
Write-Host "== 2/4 Sign-in" -ForegroundColor Cyan
$null = & $gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not signed in. Run this yourself, then re-run the script:" -ForegroundColor Yellow
    Write-Host "    gh auth login --scopes repo,workflow"
    exit 1
}
Write-Host "Signed in."

Write-Host "== 3/4 gh-aw extension ($GhAwVersion)" -ForegroundColor Cyan
$extensions = (& $gh extension list 2>&1) | Out-String
if ($extensions -notmatch "gh-aw") {
    & $gh extension install github/gh-aw --pin $GhAwVersion
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Extension install failed (see above)." -ForegroundColor Red
        exit 1
    }
}
& $gh aw version

# Diagnostics only: report problems, but do not stop on them.
Write-Host "== 4/4 Repository check (run from the repo root)" -ForegroundColor Cyan
& $gh aw doctor
& $gh aw secrets bootstrap --non-interactive

Write-Host ""
Write-Host "Done. If ANTHROPIC_API_KEY is listed as missing, create an API key at console.anthropic.com" -ForegroundColor Green
Write-Host "(Billing needs a few dollars of credit), then run:  gh aw secrets set ANTHROPIC_API_KEY" -ForegroundColor Green
exit 0
