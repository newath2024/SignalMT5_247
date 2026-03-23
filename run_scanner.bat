@echo off
setlocal
call "%~dp0scripts\run_scanner.bat"
exit /b %errorlevel%
