@echo off
setlocal
cd /d "%~dp0"

set "ROOT=%~dp0"
set "PYTHON_EXE="

if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%python_embedded\python.exe" set "PYTHON_EXE=%ROOT%python_embedded\python.exe"

if not defined PYTHON_EXE (
  echo [ERROR] No local Python runtime was found.
  exit /b 1
)

"%PYTHON_EXE%" "%ROOT%tools\portable\health_check.py" --launch
pause
exit /b %errorlevel%
