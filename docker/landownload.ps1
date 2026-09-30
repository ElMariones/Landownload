# Landownload launcher: starts or stops the Docker app and its public Tailscale address.
#   landownload.ps1 start | stop | shortcuts
param([ValidateSet('start', 'stop', 'shortcuts')][string]$Action = 'start')
# Docker writes normal progress to stderr, which PowerShell 5.1 would turn into terminating errors.
$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$Host.UI.RawUI.WindowTitle = 'Landownload'

function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Finish($code = 0) { Say ''; Say 'This window closes in 15 seconds.' 'DarkGray'; Start-Sleep 15; exit $code }

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        $bin = 'C:\Program Files\Docker\Docker\resources\bin'
        if (Test-Path $bin) { $env:Path += ";$bin" } else {
            Say 'Docker Desktop is not installed. Install it with:' 'Yellow'
            Say '    winget install -e --id Docker.DockerDesktop' 'White'
            Finish 1
        }
    }
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { return }
    Say 'Starting Docker Desktop...'
    Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { return }
    }
    Say 'Docker did not start. Open Docker Desktop once by hand, finish its setup, then try again.' 'Red'
    Finish 1
}

function Tailscale-Status {
    $json = docker compose exec -T tailscale tailscale status --json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) { return $null }
    return ($json | Out-String | ConvertFrom-Json)
}

if ($Action -eq 'shortcuts') {
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    foreach ($item in @(@('Start Landownload', 'start'), @('Stop Landownload', 'stop'))) {
        $link = $shell.CreateShortcut((Join-Path $desktop "$($item[0]).lnk"))
        $link.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $link.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" $($item[1])"
        $link.WorkingDirectory = $root
        $link.IconLocation = Join-Path $PSScriptRoot 'landownload.ico'
        $link.Save()
    }
    Say 'Desktop shortcuts created: "Start Landownload" and "Stop Landownload".' 'Green'
    exit 0
}

if ($Action -eq 'stop') {
    if (Get-Command docker -ErrorAction SilentlyContinue) { docker info *> $null }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -or $LASTEXITCODE -ne 0) {
        Say 'Docker is not running, so Landownload is already OFF.' 'Yellow'
        Finish
    }
    Say 'Stopping Landownload...'
    docker compose down
    Say 'Landownload is OFF. The website now tells visitors the server was turned off by the admin.' 'Yellow'
    Finish
}

Ensure-Docker
Say 'Starting Landownload (the first start builds the app and takes a few minutes)...'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Say 'Could not start the containers. See the messages above.' 'Red'; Finish 1 }

# First run only: Tailscale needs you to sign in once to give this PC its public address.
$status = $null
$openedLogin = $false
for ($i = 0; $i -lt 150; $i++) {
    $status = Tailscale-Status
    if ($status -and $status.BackendState -eq 'Running' -and $status.Self.DNSName) { break }
    if ($status -and $status.AuthURL -and -not $openedLogin) {
        Say ''
        Say 'One-time setup: sign in to Tailscale in the browser window that just opened (GitHub/Google login works).' 'Cyan'
        Start-Process $status.AuthURL
        $openedLogin = $true
    }
    Start-Sleep 2
}
if (-not ($status -and $status.BackendState -eq 'Running')) {
    Say 'Tailscale is not connected yet. Landownload works locally at http://127.0.0.1:8000; run Start again after signing in.' 'Yellow'
    Start-Process 'http://127.0.0.1:8000'
    Finish 1
}

$publicUrl = 'https://' + $status.Self.DNSName.TrimEnd('.')
Set-Content -Path (Join-Path $PSScriptRoot 'public-url.txt') -Value $publicUrl -Encoding ascii

# Wait for the app to answer locally, then check the public address.
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 3 | Out-Null; break } catch { Start-Sleep 2 }
}
$public = $false
for ($i = 0; $i -lt 10 -and -not $public; $i++) {
    try { Invoke-RestMethod "$publicUrl/api/health" -TimeoutSec 15 | Out-Null; $public = $true } catch { Start-Sleep 3 }
}

Say ''
Say 'Landownload is ON' 'Green'
Say "  This PC:  http://127.0.0.1:8000"
Say "  Anywhere: $publicUrl" 'White'
if (-not $public) {
    Say ''
    Say 'The public address is not answering yet. In the Tailscale admin console make sure that:' 'Yellow'
    Say '  1. DNS page -> HTTPS Certificates is enabled   (https://login.tailscale.com/admin/dns)'
    Say '  2. Access controls allow Funnel for this device (the default policy does)'
    Say 'Then run Start again. The first HTTPS certificate can also take a minute to be issued.'
}
Finish
