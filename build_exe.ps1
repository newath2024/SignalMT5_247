$script = Join-Path $PSScriptRoot "scripts\build_exe.ps1"
& $script
exit $LASTEXITCODE
