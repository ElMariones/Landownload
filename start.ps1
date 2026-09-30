# Run without Docker (development / quick local use): installs what is missing, builds the UI, runs the server.
# For the always-reachable setup use "Start Landownload.cmd" instead.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
}
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade -r requirements.txt
if (-not (Test-Path node_modules)) { npm install }
npm run build

Start-Process 'http://127.0.0.1:8000'
.\.venv\Scripts\python.exe -m backend
