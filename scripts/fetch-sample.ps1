$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$sampleDir = Join-Path $root "bird-data/samples"
$samplePath = Join-Path $sampleDir "cathedral-hawk-fledges.mp4"
$expectedMd5 = "0773fd7dc7eea37d693288aa3aa3413e"
New-Item -ItemType Directory -Force $sampleDir | Out-Null

if (Test-Path $samplePath) {
  $actualMd5 = (Get-FileHash -Algorithm MD5 $samplePath).Hash.ToLowerInvariant()
  if ($actualMd5 -ne $expectedMd5) { throw "Existing validation video did not match the pinned source checksum; it was not overwritten." }
} else {
  $downloadPath = "$samplePath.download"
  try {
    Invoke-WebRequest -Uri "https://archive.org/download/Flickr-5972491042/Cathedral_Hawk_Fledges-5972491042.mp4" -OutFile $downloadPath -Headers @{ "User-Agent" = "LocalBirdVideoAnalyzer/0.1 validation" }
    $actualMd5 = (Get-FileHash -Algorithm MD5 $downloadPath).Hash.ToLowerInvariant()
    if ($actualMd5 -ne $expectedMd5) { throw "Downloaded validation video checksum did not match the source listing." }
    Move-Item -LiteralPath $downloadPath -Destination $samplePath
  } finally { Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue }
}

$shortSamplePath = Join-Path $sampleDir "purple-swamphen-bath.mp4"
$shortExpectedMd5 = "19d9c2937789100fd492c4e3220e588d"
if (Test-Path $shortSamplePath) {
  $actualMd5 = (Get-FileHash -Algorithm MD5 $shortSamplePath).Hash.ToLowerInvariant()
  if ($actualMd5 -ne $shortExpectedMd5) { throw "Existing short validation video did not match the pinned source checksum; it was not overwritten." }
} else {
  $shortDownloadPath = "$shortSamplePath.download"
  try {
    Invoke-WebRequest -Uri "https://archive.org/download/Flickr-35518492523/Purple_Swamphen_taking_a_bath..-35518492523.mp4" -OutFile $shortDownloadPath -Headers @{ "User-Agent" = "LocalBirdVideoAnalyzer/0.1 validation" }
    $actualMd5 = (Get-FileHash -Algorithm MD5 $shortDownloadPath).Hash.ToLowerInvariant()
    if ($actualMd5 -ne $shortExpectedMd5) { throw "Downloaded short validation video checksum did not match the source listing." }
    Move-Item -LiteralPath $shortDownloadPath -Destination $shortSamplePath
  } finally { Remove-Item -LiteralPath $shortDownloadPath -Force -ErrorAction SilentlyContinue }
}

Write-Host "Validation clip ready: $samplePath (6.8 MB; CC BY-NC-SA 2.0)."
Write-Host "Short validation clip ready: $shortSamplePath (1.1 MB; CC BY-NC-ND 2.0; keep the source unmodified)."
