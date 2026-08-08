@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto not_installed
if not exist "frontend\node_modules" goto not_installed
start "Hanmir Backend WiFi" cmd /k call "%~dp0run_backend_hardware.bat"
start "Hanmir Frontend" cmd /k call "%~dp0run_frontend.bat"
echo Wi-Fi map server started. No UWB USB connection is required.
echo Open http://localhost:5173 in Chrome.
exit /b 0
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1