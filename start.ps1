# One-command start on Windows: installs what is missing, builds the UI, runs the server.
#   .\start.ps1           local only, http://127.0.0.1:8000
#   .\start.ps1 -Remote   also reachable from your phone through the GitHub Pages UI (needs cloudflared)
param([switch]$Remote)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 -m venv .venv } else { python -m venv .venv }
}
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade -r requirements.txt
if (-not (Test-Path node_modules)) { npm install }
npm run build

if (-not $Remote) {
    Start-Process 'http://127.0.0.1:8000'
    .\.venv\Scripts\python.exe -m backend
    exit
}

# Remote access always needs an access key; create one the first time.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$envText = Get-Content .env -Raw
$token = [regex]::Match($envText, '(?m)^LANDOWNLOAD_TOKEN=(\S+)').Groups[1].Value
if (-not $token) {
    $token = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
    Add-Content .env "`nLANDOWNLOAD_TOKEN=$token"
}
# Allow the GitHub Pages site of this repository's owner to call the server.
$owner = [regex]::Match((git remote get-url origin), 'github\.com[:/]([^/]+)/').Groups[1].Value
if ($owner -and $envText -notmatch '(?m)^LANDOWNLOAD_ORIGINS=') {
    Add-Content .env "LANDOWNLOAD_ORIGINS=https://$($owner.ToLower()).github.io"
}

$server = Start-Process .\.venv\Scripts\python.exe -ArgumentList '-m', 'backend' -PassThru -NoNewWindow
Write-Host ''
Write-Host "Access key: $token" -ForegroundColor Green
Write-Host 'Open your GitHub Pages site, paste the https://...trycloudflare.com address printed below, then the access key.'
Write-Host ''
try {
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
        cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8000
    } else {
        Write-Host 'cloudflared is not installed. Install it with:  winget install Cloudflare.cloudflared' -ForegroundColor Yellow
        Write-Host 'The server keeps running locally; press Ctrl+C to stop.'
        Wait-Process -Id $server.Id
    }
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
