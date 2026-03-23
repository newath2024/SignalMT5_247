@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo Building latest EXE...
powershell -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)

if not exist "%ROOT%\dist\OpenClawScanner\OpenClawScanner.exe" (
  echo.
  echo EXE not found after build.
  pause
  exit /b 1
)

echo.
echo Launching scanner...
start "" "%ROOT%\dist\OpenClawScanner\OpenClawScanner.exe"
