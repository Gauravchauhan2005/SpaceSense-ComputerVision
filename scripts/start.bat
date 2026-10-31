@echo off
REM SpaceSense AI - Start Script (Batch)
REM Run from the project root: scripts\start.bat

setlocal EnableDelayedExpansion

echo.
echo   SpaceSense AI
echo   Real-Time Spatial Tracking ^& Ergonomic Intelligence
echo.

REM ------------------------------------------------------------------
REM Check prerequisites
REM ------------------------------------------------------------------

python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Install Python 3.11+ and add to PATH.
    exit /b 1
)
echo [OK] Python found.

node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Node.js not found. Frontend will not start.
    set NO_FRONTEND=1
)

REM ------------------------------------------------------------------
REM Virtual environment
REM ------------------------------------------------------------------

set "PROJECT_ROOT=%~dp0.."

if not exist "%PROJECT_ROOT%\venv" (
    echo Creating virtual environment...
    python -m venv "%PROJECT_ROOT%\venv"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create venv.
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

call "%PROJECT_ROOT%\venv\Scripts\activate.bat"

REM Install dependencies
echo Installing Python dependencies...
pip install -q -r "%PROJECT_ROOT%\requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] pip install failed.
    exit /b 1
)
echo [OK] Dependencies installed.

REM ------------------------------------------------------------------
REM Create data directory
REM ------------------------------------------------------------------

if not exist "%PROJECT_ROOT%\data" (
    mkdir "%PROJECT_ROOT%\data"
    echo [OK] Created data\ directory.
)

REM ------------------------------------------------------------------
REM Copy .env if missing
REM ------------------------------------------------------------------

if not exist "%PROJECT_ROOT%\.env" (
    if exist "%PROJECT_ROOT%\.env.example" (
        copy "%PROJECT_ROOT%\.env.example" "%PROJECT_ROOT%\.env" >nul
        echo [OK] Created .env from .env.example
    )
)

REM ------------------------------------------------------------------
REM Start Backend
REM ------------------------------------------------------------------

echo.
echo Starting backend server on port 8000...
start "SpaceSense Backend" cmd /k "cd /d "%PROJECT_ROOT%" && call venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

REM ------------------------------------------------------------------
REM Start Frontend
REM ------------------------------------------------------------------

if not defined NO_FRONTEND (
    if exist "%PROJECT_ROOT%\frontend\package.json" (
        echo Installing frontend dependencies...
        cd /d "%PROJECT_ROOT%\frontend"
        call npm install --silent 2>nul
        echo Starting frontend dev server...
        start "SpaceSense Frontend" cmd /k "cd /d "%PROJECT_ROOT%\frontend" && npm run dev"
    ) else (
        echo [WARNING] frontend\package.json not found. Skipping frontend.
    )
)

REM ------------------------------------------------------------------
REM Summary
REM ------------------------------------------------------------------

echo.
echo ============================================
echo   SpaceSense AI is starting!
echo ============================================
echo.
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
if not defined NO_FRONTEND (
    echo   Frontend:     http://localhost:5173
)
echo.
echo Close this window or press Ctrl+C to stop.
pause
