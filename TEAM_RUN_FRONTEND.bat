@echo off
setlocal EnableExtensions
cd /d "%~dp0frontend"

if not exist "node_modules" (
  echo Frontend packages are missing. Run TEAM_SETUP_WINDOWS.bat first.
  exit /b 1
)

echo Frontend running on http://localhost:5174
echo For a phone or tablet, use the Network URL shown below and connect to the same Wi-Fi.
call npm.cmd run dev
