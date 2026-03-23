@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%~dp0"
if not defined OPENCLAW_PORTABLE_ROOT set "OPENCLAW_PORTABLE_ROOT=%ROOT%"
if not defined OPENCLAW_HOME set "OPENCLAW_HOME=%ROOT%runtime"
if not defined OPENCLAW_LOGS_DIR set "OPENCLAW_LOGS_DIR=%ROOT%logs"
if not defined OPENCLAW_MT5_TERMINAL set "OPENCLAW_MT5_TERMINAL=%ROOT%mt5_portable\terminal64.exe"
if not defined OPENCLAW_BOT_RUN_MODE set "OPENCLAW_BOT_RUN_MODE=headless"
if not defined OPENCLAW_BOT_RESTART_DELAY_SEC set "OPENCLAW_BOT_RESTART_DELAY_SEC=10"

set "PYTHON_EXE=%OPENCLAW_PYTHON_EXE%"
if not defined PYTHON_EXE if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%python_embedded\python.exe" set "PYTHON_EXE=%ROOT%python_embedded\python.exe"

if not defined PYTHON_EXE (
  echo [ERROR] restart_bot.bat could not find a local Python runtime.
  exit /b 1
)

if not exist "%OPENCLAW_LOGS_DIR%" mkdir "%OPENCLAW_LOGS_DIR%"
set "SUPERVISOR_LOG=%OPENCLAW_LOGS_DIR%\supervisor.log"

set "BOT_ARGS="
if /I "%OPENCLAW_BOT_RUN_MODE%"=="headless" set "BOT_ARGS=--headless"
if defined OPENCLAW_APP_ARGS set "BOT_ARGS=%BOT_ARGS% %OPENCLAW_APP_ARGS%"

:loop
call :timestamp NOW
echo [%NOW%] Launching bot with %PYTHON_EXE% %BOT_ARGS%>>"%SUPERVISOR_LOG%"
"%PYTHON_EXE%" "%ROOT%main.py" %BOT_ARGS%
set "EXITCODE=%ERRORLEVEL%"
call :timestamp NOW
echo [%NOW%] Bot exited with code %EXITCODE%>>"%SUPERVISOR_LOG%"

if "%EXITCODE%"=="0" (
  echo [%NOW%] Bot exited normally. Supervisor will stop.>>"%SUPERVISOR_LOG%"
  exit /b 0
)

echo [%NOW%] Bot crashed or stopped unexpectedly. Restarting in %OPENCLAW_BOT_RESTART_DELAY_SEC%s...>>"%SUPERVISOR_LOG%"
timeout /t %OPENCLAW_BOT_RESTART_DELAY_SEC% /nobreak >nul
goto loop

:timestamp
for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyy-MM-dd HH:mm:ss\")"') do set "%~1=%%I"
goto :eof
