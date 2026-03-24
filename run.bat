@echo off
setlocal
cd /d "%~dp0"

set "ROOT=%~dp0"
set "PYTHON_EXE="
set "MODE_ARG="

if /I "%~1"=="--desktop" set "MODE_ARG=--desktop"
if /I "%~1"=="desktop" set "MODE_ARG=--desktop"
if /I "%~1"=="--ui" set "MODE_ARG=--desktop"
if /I "%~1"=="ui" set "MODE_ARG=--desktop"
if /I "%~1"=="--headless" set "MODE_ARG=--headless"
if /I "%~1"=="headless" set "MODE_ARG=--headless"
if /I "%~1"=="--check" set "MODE_ARG=--check"
if /I "%~1"=="check" set "MODE_ARG=--check"

if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%python_embedded\python.exe" set "PYTHON_EXE=%ROOT%python_embedded\python.exe"

if not defined PYTHON_EXE (
  echo [ERROR] No local Python runtime was found.
  echo Expected one of:
  echo   %ROOT%.venv\Scripts\python.exe
  echo   %ROOT%python_embedded\python.exe
  echo.
  echo Prepare the bundle on the source machine first. See prepare_portable.md
  pause
  exit /b 1
)

if /I "%MODE_ARG%"=="--check" (
  "%PYTHON_EXE%" "%ROOT%scripts\portable\health_check.py" --launch
  exit /b %errorlevel%
)

if defined MODE_ARG (
  "%PYTHON_EXE%" "%ROOT%scripts\portable\launch_portable.py" %MODE_ARG%
) else (
  "%PYTHON_EXE%" "%ROOT%scripts\portable\launch_portable.py"
)
exit /b %errorlevel%
