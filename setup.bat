@echo off
REM One-time setup. Double-click this file once on a new PC.
REM It finds Python, creates the .venv folder, installs everything from requirements.txt
REM and runs the hardware-free selftest. Safe to run again if something went wrong.
setlocal
cd /d "%~dp0"
echo.
echo === Spark ignitor setup ===
echo.

set "PY="
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if defined PY goto :have_python
py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
if defined PY goto :have_python
py -3.10 -c "import sys" >nul 2>&1 && set "PY=py -3.10"
if defined PY goto :have_python
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if defined PY goto :have_python
python -c "import sys" >nul 2>&1 && set "PY=python"
if defined PY goto :have_python

echo ERROR: Python was not found.
echo   1. Go to https://www.python.org/downloads/ and install Python 3.12.
echo   2. In the installer, tick "Add python.exe to PATH".
echo   3. Close this window and double-click setup.bat again.
pause
exit /b 1

:have_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10 or newer is needed. Install Python 3.12 from python.org and try again.
    pause
    exit /b 1
)
echo Using Python:
%PY% --version

if exist ".venv\Scripts\python.exe" goto :have_venv
echo.
echo Creating the virtual environment in the .venv folder...
%PY% -m venv .venv
if errorlevel 1 (
    echo ERROR: could not create the .venv folder. Check that this folder is writable.
    pause
    exit /b 1
)

:have_venv
echo.
echo Installing the packages. This can take a few minutes the first time...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: the package install failed. Read the red text above.
    echo Usually this means no internet connection, or a proxy/firewall blocks pip.
    pause
    exit /b 1
)

echo.
echo Running the selftest (no hardware needed)...
".venv\Scripts\python.exe" -m spark_ignitor selftest
if errorlevel 1 (
    echo.
    echo ERROR: the selftest failed. Send the output above to the project owner.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo  SETUP COMPLETE.
echo  To start the app, double-click START_DASHBOARD.bat
echo ==========================================================
pause
exit /b 0
