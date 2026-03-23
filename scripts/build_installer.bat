@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"
powershell -ExecutionPolicy Bypass -File "%~dp0build_installer.ps1"
if errorlevel 1 (
  echo.
  echo Installer build failed.
  pause
  exit /b 1
)
echo.
echo Installer is in dist\installer\OpenClawScannerSetup.exe
pause
