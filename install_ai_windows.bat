@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto not_installed
for /f "tokens=2" %%v in ('".venv\Scripts\python.exe" --version') do set "PYVER=%%v"
echo Current virtual environment Python: %PYVER%
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] in [(3,11),(3,12),(3,13)] else 1)"
if errorlevel 1 goto wrong_python
call ".venv\Scripts\python.exe" -m pip install -r "backend\requirements-optional-ai.txt"
if errorlevel 1 goto error
echo AI/CV packages installed. best.pt is ready in backend.
exit /b 0
:not_installed
echo ERROR: Run install_windows.bat first.
exit /b 1
:wrong_python
echo ERROR: Real YOLO requires Python 3.11-3.13. Install Python 3.12, remove the new final folder's .venv, and run install_windows.bat again.
exit /b 1
:error
echo ERROR: AI package installation failed.
exit /b 1