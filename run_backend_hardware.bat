@echo off
setlocal
set "OPERATION_MODE=hardware"
call "%~dp0run_backend.bat"
exit /b %errorlevel%