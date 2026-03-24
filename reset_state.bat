@echo off
setlocal
set "APP_HOME=%LOCALAPPDATA%\OpenClaw"
set "STATE_FILE=%APP_HOME%\data\runtime_state.json"
set "DB_FILE=%APP_HOME%\data\history.db"

echo Resetting Liquidity Sniper runtime state...
echo.

call :delete_if_exists "%STATE_FILE%"
call :delete_if_exists "%DB_FILE%"

echo.
echo Done. Config and logs were kept.
pause
exit /b 0

:delete_if_exists
if exist "%~1" (
  del /f /q "%~1"
  echo Deleted: %~1
) else (
  echo Not found: %~1
)
exit /b 0
