$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
$issFile = Join-Path $root "packaging\OpenClawScannerInstaller.iss"

& (Join-Path $root "scripts\build_exe.ps1")

if (-not $iscc -and (Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe")) {
  $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
}

if (-not $iscc -and (Test-Path "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
  $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
}

if (-not $iscc) {
  Write-Host "Inno Setup not found. Installing via winget..." -ForegroundColor Yellow
  winget install --id JRSoftware.InnoSetup -e --accept-source-agreements --accept-package-agreements --silent --disable-interactivity
  $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
}

if (-not $iscc) {
  throw "Inno Setup compiler (ISCC.exe) was not found. Install Inno Setup 6 and run build_installer.ps1 again."
}

Push-Location $root
& $iscc $issFile
Pop-Location

$installerOutput = Join-Path $root "dist\installer\OpenClawScannerSetup.exe"
if (-not (Test-Path $installerOutput)) {
  throw "Installer output was not created: $installerOutput"
}

Write-Host ""
Write-Host "Installer build complete:" -ForegroundColor Green
Write-Host "  $installerOutput"
