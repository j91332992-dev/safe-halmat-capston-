@echo off
setlocal
cd /d "%~dp0"
set "UWB_PORT=%~1"
if not defined UWB_PORT set "UWB_PORT=COM6"
if not exist ".venv\Scripts\python.exe" goto not_installed
if not exist "frontend\node_modules" goto not_installed
start "Hanmir Backend Hardware" cmd /k call "%~dp0run_backend_hardware.bat"
start "Hanmir Frontend" cmd /k call "%~dp0run_frontend.bat"
timeout /t 3 /nobreak >nul
start "Hanmir UWB Bridge" cmd /k call "%~dp0run_uwb_bridge.bat" "%UWB_PORT%"
echo Hardware map started. TAG port: %UWB_PORT%
echo Open http://localhost:5173 in Chrome.
exit /b 0
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1