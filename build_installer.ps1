$script = Join-Path $PSScriptRoot "scripts\build_installer.ps1"
& $script
exit $LASTEXITCODE
