$ErrorActionPreference = "Stop"

$python = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
$specFile = Join-Path $PSScriptRoot "OpenClawScanner.spec"
$envFile = Join-Path $PSScriptRoot ".env"
$notesFile = Join-Path $PSScriptRoot "PORTABLE_SETUP.txt"
$iconFile = Join-Path $PSScriptRoot "assets\liquidity_sniper.ico"
$iconPngFile = Join-Path $PSScriptRoot "assets\liquidity_sniper_icon.png"
$distDir = Join-Path $PSScriptRoot "dist\OpenClawScanner"
$resetScript = Join-Path $distDir "ResetScannerState.bat"

Get-ChildItem -Path $PSScriptRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $PSScriptRoot -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

& $python -m pip install --upgrade pyinstaller PySide6
& $python -m PyInstaller --noconfirm --clean $specFile

if (-not (Test-Path $distDir)) {
  throw "Portable output folder was not created: $distDir"
}

if (Test-Path $envFile) {
  Copy-Item $envFile (Join-Path $distDir ".env") -Force
}

if (Test-Path $notesFile) {
  Copy-Item $notesFile (Join-Path $distDir "PORTABLE_SETUP.txt") -Force
}

if (Test-Path $iconFile) {
  Copy-Item $iconFile (Join-Path $distDir "liquidity_sniper.ico") -Force
}

if (Test-Path $iconPngFile) {
  Copy-Item $iconPngFile (Join-Path $distDir "liquidity_sniper_icon.png") -Force
}

@'
@echo off
setlocal
set "APP_HOME=%LOCALAPPDATA%\OpenClaw"
set "STATE_FILE=%APP_HOME%\data\runtime_state.json"
set "DB_FILE=%APP_HOME%\data\history.db"

echo Resetting Liquidity Sniper runtime state...
if exist "%STATE_FILE%" del /f /q "%STATE_FILE%"
if exist "%DB_FILE%" del /f /q "%DB_FILE%"
echo Done. Config and logs were kept.
pause
'@ | Set-Content -Path $resetScript -Encoding ASCII
