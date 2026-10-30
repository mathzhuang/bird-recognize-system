param([switch]$Mock, [int]$ApiPort = 8000, [int]$FrontendPort = 5173)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend/.venv/Scripts/python.exe"
$node = (Get-Command node.exe -ErrorAction Stop).Source
$vite = Join-Path $root "frontend/node_modules/vite/bin/vite.js"
if (-not (Test-Path $python)) { throw "backend/.venv is missing. Run .\scripts\setup.ps1 first." }
if (-not (Test-Path $vite)) { throw "frontend dependencies are missing. Run .\scripts/setup.ps1 first." }

function Find-FreePort([int]$requested) {
  for ($candidate = $requested; $candidate -lt [Math]::Min(65535, $requested + 100); $candidate++) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
    try {
      $listener.Start()
      $listener.Stop()
      return $candidate
    } catch {
      try { $listener.Stop() } catch { }
    }
  }
  throw "No free loopback port was found near $requested."
}

$ApiPort = Find-FreePort $ApiPort
$FrontendPort = Find-FreePort $FrontendPort
$dataName = if ($ApiPort -eq 8000) { "bird-data" } else { "bird-data-$ApiPort" }
$dataDir = Join-Path $root $dataName
$logDir = Join-Path $dataDir "logs"
$stateDir = Join-Path $root ".local-run"
$statePath = Join-Path $stateDir "services.json"
New-Item -ItemType Directory -Force $logDir, $stateDir | Out-Null

if (Test-Path $statePath) {
  $oldState = Get-Content -Raw -Encoding UTF8 $statePath | ConvertFrom-Json
  $oldProcesses = @($oldState.api, $oldState.frontend) | Where-Object {
    $process = Get-Process -Id $_.id -ErrorAction SilentlyContinue
    $process -and $process.StartTime.ToUniversalTime().Ticks -eq [long]$_.start_ticks
  }
  if ($oldProcesses.Count -gt 0) { throw "A previous local service is still running. Stop it with .\scripts\stop.ps1 first." }
  Remove-Item -LiteralPath $statePath
}

$previousEnvironment = @{
  BIRD_DATA_DIR = $env:BIRD_DATA_DIR
  BIRD_DETECTOR = $env:BIRD_DETECTOR
  VITE_API_TARGET = $env:VITE_API_TARGET
  VITE_USE_MOCK = $env:VITE_USE_MOCK
}
$backend = $null
$frontend = $null
try {
  $env:BIRD_DATA_DIR = $dataDir
  $env:BIRD_DETECTOR = if ($Mock) { "mock" } else { "ultralytics" }
  $env:VITE_API_TARGET = "http://127.0.0.1:$ApiPort"
  if ($Mock) { $env:VITE_USE_MOCK = "true" } else { Remove-Item Env:VITE_USE_MOCK -ErrorAction SilentlyContinue }

  $backend = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$ApiPort"
  ) -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "api-$ApiPort.stdout.log") `
    -RedirectStandardError (Join-Path $logDir "api-$ApiPort.stderr.log")
  $frontend = Start-Process -FilePath $node -ArgumentList @(
    ('"' + $vite + '"'), "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort"
  ) -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "vite-$FrontendPort.stdout.log") `
    -RedirectStandardError (Join-Path $logDir "vite-$FrontendPort.stderr.log")

  $apiReady = $false
  $frontendReady = $false
  for ($attempt = 0; $attempt -lt 80; $attempt++) {
    if (-not $backend.HasExited -and -not $apiReady) {
      try { $apiReady = (Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 1).status -eq "ok" } catch { }
    }
    if (-not $frontend.HasExited -and -not $frontendReady) {
      try { $frontendReady = (Invoke-WebRequest "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200 } catch { }
    }
    if ($apiReady -and $frontendReady) { break }
    Start-Sleep -Milliseconds 250
  }
  if (-not $apiReady -or -not $frontendReady) { throw "A local service did not become ready. Check logs in $logDir." }

  $apiProcess = Get-Process -Id $backend.Id
  $frontendProcess = Get-Process -Id $frontend.Id
  [ordered]@{
    api = [ordered]@{ id = $backend.Id; start_ticks = $apiProcess.StartTime.ToUniversalTime().Ticks; path = $apiProcess.Path }
    frontend = [ordered]@{ id = $frontend.Id; start_ticks = $frontendProcess.StartTime.ToUniversalTime().Ticks; path = $frontendProcess.Path }
    api_port = $ApiPort
    frontend_port = $FrontendPort
    data_dir = $dataDir
    detector = $env:BIRD_DETECTOR
  } | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $statePath

  if (-not $Mock -and -not (Test-Path (Join-Path $root "backend/models/yolo11n.pt"))) {
    Write-Warning "YOLO11n weights are not present. Analysis will show setup guidance; use .\scripts\setup.ps1 -WithDetector to install them or start with -Mock."
  }
  Write-Host "Backend:  http://127.0.0.1:$ApiPort"
  Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
  Write-Host "Detector: $env:BIRD_DETECTOR"
  Write-Host "Data:     $dataDir"
  Write-Host "Stop both services with .\scripts\stop.ps1."
} catch {
  foreach ($process in @($frontend, $backend)) {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
  }
  throw
} finally {
  foreach ($name in $previousEnvironment.Keys) {
    if ($null -eq $previousEnvironment[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
    else { Set-Item "Env:$name" $previousEnvironment[$name] }
  }
}
