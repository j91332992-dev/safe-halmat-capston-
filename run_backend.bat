@echo off
setlocal
cd /d "%~dp0backend"
if not exist "..\.venv\Scripts\python.exe" goto not_installed
echo Backend: http://127.0.0.1:8000
call "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
exit /b %errorlevel%
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1
