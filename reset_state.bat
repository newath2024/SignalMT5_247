@echo off
setlocal
call "%~dp0scripts\reset_state.bat"
exit /b %errorlevel%
