@echo off
REM Start GreenRoute Backend (Windows)

cd /d "%~dp0backend"

REM Check if venv exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q

REM Check for .env
if not exist ".env" (
    echo ERROR: .env file missing. Copy .env.example to .env and add your Supabase credentials.
    pause
    exit /b 1
)

echo Starting backend on http://localhost:5001
python app.py
