@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto not_installed
timeout /t 3 /nobreak >nul
call ".venv\Scripts\python.exe" "simulator\main.py"
exit /b %errorlevel%
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1
