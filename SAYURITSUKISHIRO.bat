@echo off
setlocal
cd /d "%~dp0"
REM Use relative paths so launching from a USB/HDD/SSD drive works.
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
    echo Python 3 is required. Install Python or add a matching portable runtime.
    pause
    exit /b 1
)
REM Apply files staged from the left-hand Update Project menu.
"%SAYURI_PY%" -m sayuri.updater --apply
if errorlevel 1 (
    echo Update failed. Sayuri did not start to avoid inconsistent files.
    pause
    exit /b 1
)
echo SAYURI TSUKISHIRO v0.0.0
start "" "http://127.0.0.1:8765"
"%SAYURI_PY%" -m sayuri.web
if errorlevel 1 pause
endlocal
