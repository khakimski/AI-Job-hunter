@echo off
title JobPilot AI Launcher 🚀
color 0A

echo ===================================================
echo               JobPilot AI Launcher 🚀
echo ===================================================
echo.

:: Change directory to current batch file location
cd /d "%~dp0"
set PYTHONPATH=.

echo [1/3] Checking dependencies...
python -m pip install -r backend\requirements.txt --quiet

echo.
echo [2/3] Starting JobPilot AI Backend and Web Dashboard...
echo Dashboard will be available at: http://localhost:8000
echo.

:: Open default browser
start http://localhost:8000

:: Start Uvicorn server
python -m uvicorn backend.main:app --reload --port 8000

pause
