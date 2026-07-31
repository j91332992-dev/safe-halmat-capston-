@echo off
setlocal
cd /d "%~dp0frontend"
if not exist "node_modules" goto not_installed
echo Frontend: http://127.0.0.1:5173
call npm.cmd run dev
exit /b %errorlevel%
:not_installed
echo ERROR: Run install_windows.bat first.
pause
exit /b 1
