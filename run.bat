@echo off
setlocal
cd /d "%~dp0"
set PORT=9000
if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo Created .env from .env.example.
    echo IMPORTANT: Edit .env and set a unique ADMIN_PASS and SESSION_SECRET before public hosting.
  ) else (
    echo ERROR: .env.example is missing.
    goto error
  )
)
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error
start "Asian Jewellery" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:9000/#Shop"
".venv\Scripts\python.exe" app.py
pause
exit /b 0
:error
echo Setup failed. Install Python 3.10 or newer and check your internet connection.
pause
exit /b 1
