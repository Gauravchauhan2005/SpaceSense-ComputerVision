# SpaceSense AI - Start Script
# Run from the project root: .\scripts\start.ps1

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "  SpaceSense AI  " -ForegroundColor Cyan -BackgroundColor DarkBlue
Write-Host "  Real-Time Spatial Tracking & Ergonomic Intelligence  " -ForegroundColor DarkCyan
Write-Host ""

# ------------------------------------------------------------------
# Check prerequisites
# ------------------------------------------------------------------

# Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found. Install Python 3.11+ and add to PATH." -ForegroundColor Red
    exit 1
}

# Node.js (only if frontend needed)
if (-not $BackendOnly) {
    try {
        $nodeVersion = node --version 2>&1
        Write-Host "[OK] Node.js $nodeVersion" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] Node.js not found. Frontend will not start." -ForegroundColor Yellow
        $BackendOnly = $true
    }
}

# ------------------------------------------------------------------
# Virtual environment (optional check)
# ------------------------------------------------------------------

$VenvPath = Join-Path $ProjectRoot "venv"
$PythonCmd = "python"

if (Test-Path $VenvPath) {
    $ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
    if (Test-Path $ActivateScript) {
        . $ActivateScript
        Write-Host "[OK] Activated venv." -ForegroundColor Green
    }
} else {
    Write-Host "[INFO] Using system Python environment." -ForegroundColor Gray
}

# ------------------------------------------------------------------
# Create data directory if needed
# ------------------------------------------------------------------

$DataDir = Join-Path $ProjectRoot "data"
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Host "[OK] Created data/ directory." -ForegroundColor Green
}

# ------------------------------------------------------------------
# Copy .env if missing
# ------------------------------------------------------------------

$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "[OK] Created .env from .env.example" -ForegroundColor Green
}

# ------------------------------------------------------------------
# Start Backend
# ------------------------------------------------------------------

if (-not $FrontendOnly) {
    Write-Host ""
    Write-Host "Starting backend server on port $Port..." -ForegroundColor Green
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "Set-Location '$ProjectRoot'; python -m uvicorn backend.main:app --host 0.0.0.0 --port $Port --reload"
    )
}

# ------------------------------------------------------------------
# Start Frontend
# ------------------------------------------------------------------

if (-not $BackendOnly) {
    $FrontendDir = Join-Path $ProjectRoot "frontend"
    if (Test-Path (Join-Path $FrontendDir "package.json")) {
        Write-Host "Starting frontend dev server..." -ForegroundColor Green
        Start-Process powershell -ArgumentList @(
            "-NoExit",
            "-Command",
            "Set-Location '$FrontendDir'; Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; npm run dev"
        )
    } else {
        Write-Host "[WARNING] frontend/package.json not found. Skipping frontend." -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SpaceSense AI is starting!                " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
if (-not $FrontendOnly) {
    Write-Host "  Backend API:  http://localhost:$Port"        -ForegroundColor White
    Write-Host "  API Docs:     http://localhost:$Port/docs"   -ForegroundColor White
}
if (-not $BackendOnly) {
    Write-Host "  Frontend:     http://localhost:5173"          -ForegroundColor White
}
Write-Host ""
