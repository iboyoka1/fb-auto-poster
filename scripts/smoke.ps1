$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:5000'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1) Get login page to establish session and retrieve CSRF token
$loginResp = Invoke-WebRequest -Uri "$base/login" -Method Get -WebSession $session
$csrfMatch = [regex]::Match($loginResp.Content, 'window\.csrfToken\s*=\s*"([^"]+)"')
if (-not $csrfMatch.Success) { throw 'Failed to extract CSRF token from login page' }
$csrf = $csrfMatch.Groups[1].Value

# 2) Log in (demo mode accepts any user if no password configured)
$loginHeaders = @{ 'X-CSRF-Token' = $csrf; 'Content-Type' = 'application/json' }
$loginBody = @{ username = 'admin'; password = '' } | ConvertTo-Json -Compress
$login = Invoke-RestMethod -Uri "$base/login" -Method Post -WebSession $session -Headers $loginHeaders -Body $loginBody
if (-not $login.success) { throw "Login failed: $($login.error)" }

# 3) Start a post via API
$postHeaders = @{ 'X-CSRF-Token' = $csrf; 'Content-Type' = 'application/json' }
$body = @{ content = "Smoke test post $(Get-Date)" } | ConvertTo-Json -Compress
$start = Invoke-RestMethod -Uri "$base/api/post" -Method Post -WebSession $session -Headers $postHeaders -Body $body

Start-Sleep -Seconds 2

# 4) Check posting status and history
$status = Invoke-RestMethod -Uri "$base/api/posting-status" -Method Get -WebSession $session
$hist = Invoke-RestMethod -Uri "$base/api/history" -Method Get -WebSession $session

Write-Host "LOGIN:"; $login | ConvertTo-Json -Depth 5
Write-Host "START:"; $start | ConvertTo-Json -Depth 5
Write-Host "STATUS:"; $status | ConvertTo-Json -Depth 5
Write-Host "HISTORY:"; $hist | ConvertTo-Json -Depth 5
