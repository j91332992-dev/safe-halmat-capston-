@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==================================================
echo  HANMIR SMART HELMET - TEAM PC FIRST-TIME SETUP
echo ==================================================

where py >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 goto no_python
  set "PYTHON_CMD=python"
)

%PYTHON_CMD% --version
if errorlevel 1 goto no_python
where npm.cmd >nul 2>&1
if errorlevel 1 goto no_node

echo.
echo [1/3] Preparing backend Python environment...
if not exist "backend\.venv\Scripts\python.exe" %PYTHON_CMD% -m venv "backend\.venv"
if errorlevel 1 goto failed
call "backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
call "backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto failed

echo.
echo [2/3] Preparing frontend packages...
pushd "frontend"
if exist "package-lock.json" (
  call npm.cmd ci
) else (
  call npm.cmd install
)
if errorlevel 1 goto npm_failed
popd

echo.
echo [3/3] Creating local server settings if needed...
if not exist "backend\.env" copy /Y "backend\.env.example" "backend\.env" >nul

echo.
echo Setup complete.
echo Next: run TEAM_RUN_ALL.bat, then open http://localhost:5174
exit /b 0

:npm_failed
popd
goto failed
:no_python
echo ERROR: Install Python 3.10 or newer, then run this file again.
exit /b 1
:no_node
echo ERROR: Install Node.js LTS, then run this file again.
exit /b 1
:failed
echo ERROR: Setup failed. Read the error shown above.
exit /b 1
