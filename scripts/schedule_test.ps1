$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:5000'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession

# 1) Fetch login page and CSRF token
$loginResp = Invoke-WebRequest -Uri "$base/login" -Method Get -WebSession $session
$csrfMatch = [regex]::Match($loginResp.Content, 'window\.csrfToken\s*=\s*"([^"]+)"')
if (-not $csrfMatch.Success) { throw 'Failed to extract CSRF token from login page' }
$csrf = $csrfMatch.Groups[1].Value

# 2) Log in (demo mode accepts any user if no password configured)
$headers = @{ 'X-CSRF-Token' = $csrf; 'Content-Type' = 'application/json' }
$loginBody = @{ username = 'admin'; password = '' } | ConvertTo-Json -Compress
$login = Invoke-RestMethod -Uri "$base/login" -Method Post -WebSession $session -Headers $headers -Body $loginBody
if (-not $login.success) { throw "Login failed: $($login.error)" }

# 3) Choose some groups
$groups = Invoke-RestMethod -Uri "$base/api/groups" -Method Get -WebSession $session
$usernames = @()
if ($groups.success -and $groups.groups.Count -gt 0) {
  $usernames = @($groups.groups | Select-Object -First 2 | ForEach-Object { $_.username })
}

# 4) Create a schedule 5 minutes from now
$schedBody = @{ content = "Schedule test $(Get-Date)"; groups = $usernames; schedule_time = '5m'; recurring = $false; interval_hours = 24 } | ConvertTo-Json -Compress
$sched = Invoke-RestMethod -Uri "$base/api/schedule" -Method Post -WebSession $session -Headers $headers -Body $schedBody
if (-not $sched.success) { throw "Failed to create schedule: $($sched.error)" }
$id = $sched.schedule.id

Start-Sleep -Seconds 1

# 5) Pause the schedule
$pause = Invoke-RestMethod -Uri "$base/api/schedule/$id/pause" -Method Post -WebSession $session -Headers $headers
$afterPause = Invoke-RestMethod -Uri "$base/api/schedule" -Method Get -WebSession $session

# 6) Resume the schedule
$resume = Invoke-RestMethod -Uri "$base/api/schedule/$id/resume" -Method Post -WebSession $session -Headers $headers
$afterResume = Invoke-RestMethod -Uri "$base/api/schedule" -Method Get -WebSession $session

# Output
Write-Host "LOGIN:"; $login | ConvertTo-Json -Depth 5
Write-Host "SCHEDULE CREATE:"; $sched | ConvertTo-Json -Depth 6
Write-Host "AFTER PAUSE:"; $afterPause | ConvertTo-Json -Depth 6
Write-Host "AFTER RESUME:"; $afterResume | ConvertTo-Json -Depth 6
