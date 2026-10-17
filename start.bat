@echo off
REM Start Bath Solution Studio without Docker (Windows). Needs Python 3.10+ from python.org.
cd /d "%~dp0"
if not exist .venv (
  echo First run: setting up, this takes a minute...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
if "%PORT%"=="" set PORT=8000
echo.
echo Bath Solution Studio is running.
echo   On this computer:   http://localhost:%PORT%
echo   For the sales team: http://THIS-COMPUTER-IP:%PORT%   (run "ipconfig" to see the IPv4 address)
echo Keep this window open. Close it to stop the app.
echo.
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port %PORT%
pause
