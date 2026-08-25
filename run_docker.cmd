@echo off
title JobPilot AI - Docker Launcher 🐳
color 0B

echo ===================================================
echo         JobPilot AI Docker Compose Launcher 🐳
echo ===================================================
echo.

cd /d "%~dp0"

echo Starting Docker containers (Backend + PostgreSQL)...
docker compose up --build

pause
