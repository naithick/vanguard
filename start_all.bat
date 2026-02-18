@echo off
REM Start GreenRoute - Backend & Frontend (Windows)

echo.
echo   GreenRoute Mesh - Full Stack Startup
echo   =====================================
echo.
echo   This will start both backend and frontend servers.
echo   Make sure you have configured backend\.env first!
echo.

REM Start backend in new window
echo   Starting backend server...
start "GreenRoute Backend" cmd /c "%~dp0start_backend.bat"

REM Wait for backend to initialize
echo   Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

echo   Backend should be running on http://localhost:5001
echo.

REM Start frontend in current window
echo   Starting frontend server...
call "%~dp0start_frontend.bat"

echo.
echo   Shutting down... Close the Backend window manually if needed.
pause
