@echo off
setlocal
cd /d "%~dp0"

echo Building latest EXE...
powershell -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)

if not exist "%~dp0dist\OpenClawScanner\OpenClawScanner.exe" (
  echo.
  echo EXE not found after build.
  pause
  exit /b 1
)

echo.
echo Launching scanner...
start "" "%~dp0dist\OpenClawScanner\OpenClawScanner.exe"
