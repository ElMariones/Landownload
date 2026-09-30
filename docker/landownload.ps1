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
# First run only: Tailscale needs a one-time auth key to give this PC its public address.
$status = $null
for ($i = 0; $i -lt 45; $i++) {
    $status = Tailscale-Status
    if ($status -and $status.BackendState -eq 'Running' -and $status.Self.DNSName) { break }
    if ($status -and $status.BackendState -eq 'NeedsLogin' -and $i -ge 5) { break }
    Start-Sleep 2
}
if ($status -and $status.BackendState -eq 'NeedsLogin') {
    if (-not (Test-Path .env) -or -not (Select-String -Path .env -Pattern '^TS_AUTHKEY=\S' -Quiet)) {
        if (-not (Test-Path .env)) { Set-Content .env "TS_AUTHKEY=" -Encoding ascii }
        Say ''
        Say 'One-time setup: this PC needs a Tailscale auth key.' 'Cyan'
        Say '  1. On the Tailscale page that just opened, click "Generate auth key..." then "Generate key", and copy it.'
        Say '  2. Paste it after TS_AUTHKEY= in the .env file that opened in Notepad, and save.'
        Say '  3. Run Start Landownload again.'
        Start-Process 'https://login.tailscale.com/admin/settings/keys'
        Start-Process notepad.exe (Join-Path $root '.env')
    } else {
        Say 'Tailscale rejected the auth key (used or expired). Generate a new one, replace it in .env, and start again.' 'Yellow'
        Start-Process 'https://login.tailscale.com/admin/settings/keys'
    }
    Finish 1
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
    Say 'The public address is not answering yet.' 'Yellow'
    # When Funnel is off for the tailnet, the CLI prints a one-click link to turn it on.
    $probe = Start-Job { param($dir) Set-Location $dir; docker compose exec -T tailscale tailscale funnel --bg 8000 2>&1 } -ArgumentList $root
    Wait-Job $probe -Timeout 20 | Out-Null
    $enable = [regex]::Match(((Receive-Job $probe) -join "`n"), 'https://login\.tailscale\.com/f/funnel\S+').Value
    Remove-Job $probe -Force
    if ($enable) {
        Say 'Funnel is turned off for your Tailscale account. Click "Enable" on the page that just opened, then run Start again.' 'Cyan'
        Start-Process $enable
    } else {
        Say 'Check that HTTPS Certificates is enabled at https://login.tailscale.com/admin/dns, then run Start again.'
        Say 'The first HTTPS certificate can also take a minute to be issued.'
    }
}
Finish
