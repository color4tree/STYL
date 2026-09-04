[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$runtime = Join-Path $root ".styl-runtime"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source

function Stop-PortProcess {
    param([int]$Port)

    $processIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $processIds) {
        if ($processId -gt 0) {
            & cmd.exe /d /c "taskkill.exe /PID $processId /T /F >nul 2>&1"
        }
    }
}

function Get-FreePort {
    param([int]$PreferredPort)

    for ($port = $PreferredPort; $port -lt ($PreferredPort + 20); $port++) {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) {
            return $port
        }
    }

    throw "No free port was found between $PreferredPort and $($PreferredPort + 19)."
}

function Stop-StylApiProcesses {
    for ($port = 8000; $port -lt 8020; $port++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1
            if ($health.service -eq "styl-api") {
                Stop-PortProcess -Port $port
            }
        }
        catch {
            # The port is unused or belongs to another service.
        }
    }
}

function Wait-ForUrl {
    param(
        [string]$Url,
        [string]$Service,
        [int]$Attempts = 40
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            return Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw "$Service did not become ready at $Url. Check the logs in $runtime."
            }
        }
    }
}

if (-not (Test-Path $python)) {
    throw "Backend virtual environment not found. Run: python -m venv backend\.venv"
}

if (-not $npm) {
    throw "npm.cmd was not found. Install Node.js and reopen PowerShell."
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & $npm install --prefix $frontend
    if ($LASTEXITCODE -ne 0) {
        throw "npm install failed."
    }
}

New-Item -ItemType Directory -Path $runtime -Force | Out-Null

Write-Host "Stopping stale STYL servers..." -ForegroundColor Cyan
Stop-PortProcess -Port 3000
Stop-StylApiProcesses

$frontendPort = Get-FreePort -PreferredPort 3000
$apiPort = Get-FreePort -PreferredPort 8000

if ($apiPort -ne 8000) {
    Write-Host "Port 8000 is still reserved by Windows; using API port $apiPort." -ForegroundColor Yellow
}

if (-not $env:STYL_ADMIN_TOKEN) {
    $env:STYL_ADMIN_TOKEN = "local-development-token"
}

Write-Host "Starting backend..." -ForegroundColor Cyan
$backendProcess = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $apiPort) `
    -WorkingDirectory $backend `
    -RedirectStandardOutput (Join-Path $runtime "backend.log") `
    -RedirectStandardError (Join-Path $runtime "backend-error.log") `
    -PassThru

$openApi = Wait-ForUrl -Url "http://127.0.0.1:$apiPort/openapi.json" -Service "Backend"
if ($openApi.Content -notmatch '"/api/products/\{product_id\}"') {
    Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    throw "Backend started, but the product update route is missing. Check $runtime\backend-error.log."
}

Write-Host "Starting frontend..." -ForegroundColor Cyan
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$apiPort"
$frontendProcess = Start-Process -FilePath $npm `
    -ArgumentList @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", $frontendPort) `
    -WorkingDirectory $frontend `
    -RedirectStandardOutput (Join-Path $runtime "frontend.log") `
    -RedirectStandardError (Join-Path $runtime "frontend-error.log") `
    -PassThru

Wait-ForUrl -Url "http://127.0.0.1:$frontendPort/admin" -Service "Frontend" | Out-Null

Set-Content -Path (Join-Path $runtime "backend.pid") -Value $backendProcess.Id
Set-Content -Path (Join-Path $runtime "frontend.pid") -Value $frontendProcess.Id

Write-Host ""
Write-Host "STYL is ready." -ForegroundColor Green
Write-Host "Portal: http://localhost:$frontendPort"
Write-Host "Admin:  http://localhost:$frontendPort/admin"
Write-Host "Token:  $env:STYL_ADMIN_TOKEN"
Write-Host "API:    http://localhost:$apiPort/docs"
Write-Host "Logs:   $runtime"

if (-not $NoBrowser) {
    Start-Process "http://localhost:$frontendPort/admin"
}