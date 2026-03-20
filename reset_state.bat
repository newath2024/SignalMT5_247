@echo off
setlocal
cd /d "%~dp0"

set "ROOT_WATCH=%~dp0watch_cache.json"
set "ROOT_ALERT=%~dp0alert_cache.json"
set "DIST_WATCH=%~dp0dist\watch_cache.json"
set "DIST_ALERT=%~dp0dist\alert_cache.json"

echo Resetting scanner state...
echo.

call :delete_if_exists "%ROOT_WATCH%"
call :delete_if_exists "%ROOT_ALERT%"
call :delete_if_exists "%DIST_WATCH%"
call :delete_if_exists "%DIST_ALERT%"

echo.
echo Done. Watch and alert caches were cleared.
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
