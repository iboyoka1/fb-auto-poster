$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
Push-Location $root

Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "Installing Playwright browsers (Chromium + Edge)..." -ForegroundColor Cyan
python -m playwright install chromium msedge

Write-Host "Ensuring local directories exist..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path "$root\sessions" -Force | Out-Null
New-Item -ItemType Directory -Path "$root\uploads" -Force | Out-Null

Write-Host "Setup complete." -ForegroundColor Green
Pop-Location
