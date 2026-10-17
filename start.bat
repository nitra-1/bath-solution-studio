@echo off
REM Start Bath Solution Studio without Docker (Windows). Needs Python 3.10+ from python.org.
REM To always use a particular port, change 8010 below.
cd /d "%~dp0"
if not exist .venv (
  echo First run: setting up, this takes a minute...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
if "%PORT%"=="" set PORT=8010

:checkport
netstat -ano | findstr /R /C:"TCP.*:%PORT% .*LISTENING" >nul
if not errorlevel 1 (
  echo Port %PORT% is already used by another program. Trying the next one...
  set /a PORT=%PORT%+1
  goto checkport
)

echo.
echo Bath Solution Studio is starting.
echo   On this computer:   http://localhost:%PORT%
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4"') do for /f "tokens=*" %%b in ("%%a") do echo   For the sales team: http://%%b:%PORT%
echo   (If several addresses are listed, use the one on your office network.)
echo Keep this window open. Close it to stop the app.
echo.
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port %PORT%
echo.
echo The app stopped. If you see an error above, send it to your admin.
pause
