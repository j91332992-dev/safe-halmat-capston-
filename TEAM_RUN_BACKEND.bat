@echo off
setlocal EnableExtensions
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo Backend environment is missing. Run TEAM_SETUP_WINDOWS.bat first.
  exit /b 1
)
if not exist ".env" copy /Y ".env.example" ".env" >nul

echo Backend running on http://0.0.0.0:8000
echo Keep this window open while using the dashboard.
call ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
