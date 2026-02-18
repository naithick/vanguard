@echo off
REM Start GreenRoute Frontend (Windows)

cd /d "%~dp0frontend"

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing npm packages...
    npm install
)

echo Starting frontend on http://localhost:5173
npm run dev
