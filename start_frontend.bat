@echo off
REM Start GreenRoute Frontend (Windows)

echo.
echo   GreenRoute Frontend Setup
echo   ==========================
echo.

REM Check for Node.js
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [X] Node.js not found!
    echo.
    echo   Please install Node.js 18+ from:
    echo     https://nodejs.org/
    echo.
    echo   Or run: winget install OpenJS.NodeJS
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VER=%%i
echo   [OK] Node.js %NODE_VER% found

cd /d "%~dp0frontend"

REM Install dependencies if needed
if not exist "node_modules" (
    echo.
    echo   Installing npm packages ^(first time setup^)...
    npm install
)

echo.
echo   Starting frontend on http://localhost:5173
echo   Press Ctrl+C to stop
echo.
npx vite --host
