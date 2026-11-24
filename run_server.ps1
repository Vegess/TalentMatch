Set-Location $PSScriptRoot\backend
if (Test-Path .venv\Scripts\Activate.ps1) { . .venv\Scripts\Activate.ps1 }
Write-Host "  App: http://localhost:8000/   API docs: http://localhost:8000/docs" -ForegroundColor Green
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
