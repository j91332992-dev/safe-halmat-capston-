@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto not_installed
if not exist "frontend\node_modules" goto not_installed
start "Hanmir Integrated Backend" cmd /k call "%~dp0run_backend_hardware.bat"
start "Hanmir Integrated Frontend" cmd /k call "%~dp0run_frontend.bat"
echo Backend and frontend started in hardware mode.
echo Power on UWB anchors, UWB TAG, and AV helmet device.
echo Open http://localhost:5173
exit /b 0
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1