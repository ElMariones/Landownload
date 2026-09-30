#!/usr/bin/env sh
# One-command start on macOS/Linux: installs what is missing, builds the UI, runs the server.
set -e
cd "$(dirname "$0")"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade -r requirements.txt
[ -d node_modules ] || npm install
npm run build

echo "Landownload → http://127.0.0.1:8000"
exec .venv/bin/python -m backend
