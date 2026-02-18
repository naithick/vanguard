@echo off
REM Start GreenRoute Backend (Windows)

echo.
echo   GreenRoute Backend Setup
echo   =========================
echo.

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [X] Python not found!
    echo.
    echo   Please install Python 3.9+ from:
    echo     https://www.python.org/downloads/
    echo.
    echo   Or run: winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo   [OK] %PY_VER% found

cd /d "%~dp0backend"

REM Create venv if needed
if not exist "venv" (
    echo.
    echo   Creating virtual environment ^(first time setup^)...
    python -m venv venv
)

REM Activate venv
echo   [OK] Activating virtual environment
call venv\Scripts\activate

REM Install dependencies
if not exist "venv\.installed" (
    echo   Installing Python packages...
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    echo. > venv\.installed
    echo   [OK] Dependencies installed
) else (
    echo   [OK] Dependencies already installed
)

REM Check for .env
if not exist ".env" (
    echo.
    echo   [!] Configuration needed!
    echo.
    echo   1. Copy the example config:
    echo      copy .env.example .env
    echo.
    echo   2. Edit .env and add your Supabase credentials:
    echo      SUPABASE_URL=https://your-project.supabase.co
    echo      SUPABASE_SERVICE_KEY=your-service-key
    echo.
    echo   Get credentials from: https://supabase.com/dashboard
    pause
    exit /b 1
)

echo.
echo   Starting backend on http://localhost:5001
echo   Press Ctrl+C to stop
echo.
python app.py
