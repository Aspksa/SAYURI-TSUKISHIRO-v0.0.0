@echo off
setlocal
cd /d "%~dp0"
REM Paths are relative to this BAT, including when launched from a USB drive.
set "SAYURI_PY="
if exist "%~dp0runtime\python\python.exe" set "SAYURI_PY=%~dp0runtime\python\python.exe"
if not defined SAYURI_PY (
    where py >nul 2>&1
    if not errorlevel 1 set "SAYURI_PY=py"
)
if not defined SAYURI_PY (
    where python >nul 2>&1
    if not errorlevel 1 set "SAYURI_PY=python"
)
if not defined SAYURI_PY (
    echo Python is not found.
    echo Install Python 3 or add a matching Windows portable Python runtime
    echo in runtime\python\python.exe on this drive.
    pause
    exit /b 1
)
echo SAYURI TSUKISHIRO v0.0.0
echo Opening local web page: http://127.0.0.1:8765
start "" "http://127.0.0.1:8765"
"%SAYURI_PY%" -m sayuri.web
if errorlevel 1 pause
endlocal
