param([switch]$WithDetector)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root "backend/.venv"
$python = Join-Path $venv "Scripts/python.exe"
if (-not (Test-Path $python)) { python -m venv $venv }
$lockFile = if ($WithDetector) { "requirements-detector.lock" } else { "requirements.lock" }
& $python -m pip install -r (Join-Path $root "backend/$lockFile")
Push-Location (Join-Path $root "frontend")
try { npm.cmd ci; npm.cmd run api:types } finally { Pop-Location }
if ($WithDetector) {
  $modelDir = Join-Path $root "backend/models"
  New-Item -ItemType Directory -Force $modelDir | Out-Null
  $modelPath = Join-Path $modelDir "yolo11n.pt"
  $expectedHash = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
  if (Test-Path $modelPath) {
    $actualHash = (Get-FileHash -Algorithm SHA256 $modelPath).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) { throw "Existing yolo11n.pt has a different checksum; it was not overwritten." }
  } else {
    $downloadPath = "$modelPath.download"
    try {
      Invoke-WebRequest -Uri "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt" -OutFile $downloadPath
      $actualHash = (Get-FileHash -Algorithm SHA256 $downloadPath).Hash.ToLowerInvariant()
      if ($actualHash -ne $expectedHash) { throw "Downloaded model checksum did not match the pinned reference." }
      Move-Item -LiteralPath $downloadPath -Destination $modelPath
    } finally { Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue }
  }
}
Write-Host "Setup complete. Use .\scripts\start.ps1 or .\scripts\start.ps1 -Mock."
