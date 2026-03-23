@echo off
setlocal
call "%~dp0scripts\build_installer.bat"
exit /b %errorlevel%
