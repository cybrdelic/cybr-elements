param(
  [ValidateSet('original','volume','sparse')][string]$Simulation='original',
  [string]$Preset='sooty-plume',
  [ValidateRange(1024,65535)][int]$Port=8767
)
$ErrorActionPreference='Stop'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$siteRoot=Join-Path $repoRoot 'outputs/cybrdelic-type'
$outputRoot=Join-Path $repoRoot 'output/fire-demo'
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$chromeCandidates=@(
  (Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'),
  (Join-Path ${env:ProgramFiles(x86)} 'Google/Chrome/Application/chrome.exe'),
  (Join-Path $env:LOCALAPPDATA 'Google/Chrome/Application/chrome.exe')
)
$chrome=$chromeCandidates | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
if(!$chrome){throw 'Chrome was not found in its standard installation locations.'}
$entry="http://127.0.0.1:$Port/elements/motion/bending/sigils/02/fire-live/"
try {$ready=(Invoke-WebRequest $entry -TimeoutSec 3).StatusCode -eq 200} catch {$ready=$false}
if(!$ready){
  $python=(Get-Command python -ErrorAction Stop).Source
  $serverArguments=@('-m','http.server',"$Port",'--bind','127.0.0.1','--directory',('"{0}"' -f $siteRoot))
  Start-Process -FilePath $python -ArgumentList $serverArguments -WindowStyle Hidden -RedirectStandardOutput (Join-Path $outputRoot 'server.log') -RedirectStandardError (Join-Path $outputRoot 'server-error.log') | Out-Null
  for($attempt=0;$attempt -lt 30;$attempt++){
    try {$ready=(Invoke-WebRequest $entry -TimeoutSec 1).StatusCode -eq 200} catch {$ready=$false}
    if($ready){break};Start-Sleep -Milliseconds 200
  }
  if(!$ready){throw 'The local Fire Studio server did not become ready.'}
}
$profile=Join-Path $outputRoot 'chrome-profile'
$url=$entry+'?simulation='+$Simulation+'&preset='+[Uri]::EscapeDataString($Preset)+'&room=1&lighting=fully-lit'
# A dedicated profile makes these process-start flags take effect even when
# the user's ordinary Chrome session is already running on the integrated GPU.
$arguments=@(('--user-data-dir="{0}"' -f $profile),'--force-high-performance-gpu','--force_high_performance_gpu','--use-webgpu-power-preference=force-high-performance','--new-window',('"{0}"' -f $url))
# This is the interactive browser explicitly opened by the launcher user.
Start-Process -FilePath $chrome -ArgumentList $arguments | Out-Null
Write-Output "Opened $url with a separate Chrome profile and high-performance GPU preference."
