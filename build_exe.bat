@echo off
setlocal
call "%~dp0scripts\build_exe.bat"
exit /b %errorlevel%
