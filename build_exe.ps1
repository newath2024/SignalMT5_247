$ErrorActionPreference = "Stop"

$python = "C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"

& $python -m pip install --upgrade pyinstaller
& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name OpenClawScanner `
  --hidden-import MetaTrader5 `
  --hidden-import matplotlib.backends.backend_agg `
  main.py

if (Test-Path ".env") {
  Copy-Item ".env" "dist\\.env" -Force
}
