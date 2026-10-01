@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" goto not_ready
if not exist "frontend\node_modules" goto not_ready

start "HANMIR Backend" cmd /k call "%~dp0TEAM_RUN_BACKEND.bat"
start "HANMIR Frontend" cmd /k call "%~dp0TEAM_RUN_FRONTEND.bat"
echo Backend and frontend windows were opened.
echo Open http://localhost:5174 after the frontend reports ready.
echo Run TEAM_RUN_SIMULATOR.bat separately for virtual helmet data.
exit /b 0

:not_ready
echo Setup is required. Run TEAM_SETUP_WINDOWS.bat first.
exit /b 1
