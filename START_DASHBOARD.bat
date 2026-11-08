@echo off
REM Double-click to start the dashboard, then open http://localhost:8080 in your browser.
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python -m spark_ignitor dashboard
pause
