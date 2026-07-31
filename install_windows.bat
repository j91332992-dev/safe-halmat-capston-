@echo off
setlocal
cd /d "%~dp0"
echo [1/4] Checking Python...
where py >nul 2>&1
if errorlevel 1 goto use_python
set "PYTHON_CMD=py -3"
goto python_ready
:use_python
where python >nul 2>&1
if errorlevel 1 goto no_python
set "PYTHON_CMD=python"
:python_ready
%PYTHON_CMD% --version
if errorlevel 1 goto no_python
echo [2/4] Creating Python virtual environment...
if not exist ".venv\Scripts\python.exe" %PYTHON_CMD% -m venv .venv
if errorlevel 1 goto error
echo [3/4] Installing backend packages...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
call ".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto error
echo [4/4] Installing frontend packages...
where npm >nul 2>&1
if errorlevel 1 goto no_node
pushd "frontend"
call npm.cmd install
if errorlevel 1 goto npm_error
popd
echo Installation completed. Run run_all.bat next.
exit /b 0
:npm_error
popd
goto error
:no_python
echo ERROR: Python 3.11 or newer is required.
exit /b 1
:no_node
echo ERROR: Node.js and npm are required.
exit /b 1
:error
echo ERROR: Installation failed. Review the message above.
exit /b 1
