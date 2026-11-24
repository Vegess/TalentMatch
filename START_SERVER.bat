@echo off
title TalentMatch - server
cd /d "%~dp0backend"
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat
echo  App: http://localhost:8000/    API docs: http://localhost:8000/docs
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
