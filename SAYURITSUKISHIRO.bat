@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python 3 is required. Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PY=python"
)
if "%SAYURI_LAN%"=="" set "SAYURI_LAN=1"
echo Starting SAYURI TSUKISHIRO...
echo To access from a device on the same Wi-Fi, use this computer's IPv4 address and port 8765.
echo Find IPv4 using ipconfig. Keep this window open.
%PY% -m sayuri.app
if errorlevel 1 pause
endlocal
