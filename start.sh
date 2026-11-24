#!/usr/bin/env bash
# macOS / Linux: first-time setup and start. Needs Python 3.10+ (Node 20+ only if you change the frontend).
set -e
cd "$(dirname "$0")/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -f talentmatch.db ] || python seed_demo.py
if [ ! -f ../frontend/dist/index.html ] && command -v npm >/dev/null; then (cd ../frontend && npm ci && npm run build); fi
echo "App: http://localhost:8000/   API docs: http://localhost:8000/docs"
echo "Admin: admin@talentmatch.dev / Admin@12345 · Client: priya@technova.in / Demo@1234 · Freelancer: rahul.verma@mail.com / Demo@1234"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
