@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"
powershell -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"
if errorlevel 1 (
  echo.
  echo Build failed.
  pause
  exit /b 1
)
echo.
echo Build complete. Portable app is in dist\OpenClawScanner\OpenClawScanner.exe
pause
