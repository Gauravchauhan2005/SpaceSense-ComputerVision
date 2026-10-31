# SpaceSense AI - Test Runner
# Usage: .\scripts\run_tests.ps1 [-Verbose] [-Coverage] [-Filter <pattern>]

param(
    [switch]$Verbose,
    [switch]$Coverage,
    [string]$Filter = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "  SpaceSense AI — Test Runner  " -ForegroundColor Cyan
Write-Host ""

# Allow scripts to run in this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Activate venv
$ActivateScript = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    . $ActivateScript
} else {
    Write-Host "[WARNING] No venv found. Using system Python." -ForegroundColor Yellow
}

# Build pytest arguments
$pytestArgs = @("backend/tests/", "--tb=short")

if ($Verbose) {
    $pytestArgs += "-v"
} else {
    $pytestArgs += "-v"
}

if ($Filter) {
    $pytestArgs += "-k"
    $pytestArgs += $Filter
}

if ($Coverage) {
    $pytestArgs += "--cov=backend"
    $pytestArgs += "--cov-report=term-missing"
}

# Run tests
Write-Host "Running: python -m pytest $($pytestArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

Push-Location $ProjectRoot
python -m pytest @pytestArgs
$testResult = $LASTEXITCODE
Pop-Location

Write-Host ""
if ($testResult -eq 0) {
    Write-Host "All tests passed!" -ForegroundColor Green
} else {
    Write-Host "Some tests failed (exit code $testResult)." -ForegroundColor Red
}

exit $testResult
