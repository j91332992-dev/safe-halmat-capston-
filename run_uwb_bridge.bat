@echo off
setlocal
cd /d "%~dp0"
set "UWB_PORT=%~1"
if not defined UWB_PORT set "UWB_PORT=COM6"
if not exist ".venv\Scripts\python.exe" goto not_installed
echo UWB TAG port: %UWB_PORT%
call ".venv\Scripts\python.exe" "uwb_live_bridge.py" --port "%UWB_PORT%"
exit /b %errorlevel%
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1