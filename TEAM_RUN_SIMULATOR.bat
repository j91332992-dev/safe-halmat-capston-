@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo Backend environment is missing. Run TEAM_SETUP_WINDOWS.bat first.
  exit /b 1
)

echo Virtual helmet simulator starting. Start TEAM_RUN_BACKEND.bat first.
call "backend\.venv\Scripts\python.exe" "simulator\main.py"
