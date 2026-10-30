$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $root ".local-run/services.json"
if (-not (Test-Path $statePath)) { Write-Host "No workspace launcher services are recorded."; exit 0 }
$state = Get-Content -Raw -Encoding UTF8 $statePath | ConvertFrom-Json
foreach ($service in @($state.frontend, $state.api)) {
  $process = Get-Process -Id $service.id -ErrorAction SilentlyContinue
  if (-not $process) { continue }
  $sameProcess = $process.StartTime.ToUniversalTime().Ticks -eq [long]$service.start_ticks -and $process.Path -ieq $service.path
  if ($sameProcess) { Stop-Process -Id $process.Id -Force; Write-Host "Stopped PID $($process.Id)." }
  else { Write-Warning "PID $($service.id) no longer matches the recorded service; it was left running." }
}
Remove-Item -LiteralPath $statePath
