@echo off
REM TalentMatch - first-time setup and start (safe to run every time). Needs Python 3.10+.
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv || (echo Python 3.10+ is required: https://www.python.org/downloads/ && pause && exit /b 1)
)
call .venv\Scripts\activate.bat
echo Installing requirements...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt || (echo pip install failed && pause && exit /b 1)
if not exist "talentmatch.db" (
  echo Loading demo data...
  python seed_demo.py
)
if not exist "..\frontend\dist\index.html" (
  where npm >nul 2>nul && (pushd ..\frontend && call npm ci && call npm run build && popd) || echo Node.js not found - the web app is not built. API docs still work at /docs.
)
echo.
echo  App:      http://localhost:8000/
echo  API docs: http://localhost:8000/docs
echo  Admin:    admin@talentmatch.dev / Admin@12345
echo  Client:   priya@technova.in / Demo@1234     Freelancer: rahul.verma@mail.com / Demo@1234
echo  Keep this window open. Press Ctrl+C to stop.
echo.
start "" http://localhost:8000/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
