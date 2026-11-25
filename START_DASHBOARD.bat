@echo off
REM Double-click to start the dashboard. Run setup.bat once first.
REM It uses port 8080, or the next free port if 8080 is taken, and opens the browser for you.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The app is not set up yet.
    echo Double-click setup.bat first, then start this file again.
    pause
    exit /b 1
)

REM Find the first free port starting at 8080
set "PORT="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$p=8080; while (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $p++ }; $p"`) do set "PORT=%%p"
if not defined PORT set "PORT=8080"

echo.
echo Starting the dashboard on http://localhost:%PORT%
echo The browser opens in a few seconds.
echo KEEP THIS WINDOW OPEN while you use the page. Press Ctrl+C here to stop.
echo.

REM Open the browser after a short wait, while the server starts
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 6; Start-Process 'http://localhost:%PORT%'"

".venv\Scripts\python.exe" -m spark_ignitor dashboard --port %PORT%
echo.
echo The dashboard has stopped.
pause
