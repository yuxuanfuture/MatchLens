param(
    [ValidateRange(1024, 65535)][int]$Port = 43128,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$VisionPython = Join-Path $ProjectRoot '.venv-vision-windows\Scripts\python.exe'
$OutputFolder = Join-Path $ProjectRoot 'run-output'
$BaseUrl = "http://127.0.0.1:$Port"
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

if (-not (Test-Path -LiteralPath $VisionPython)) {
    & python (Join-Path $ProjectRoot 'scripts\setup_vision_windows.py')
    if ($LASTEXITCODE -ne 0) { throw 'Windows vision setup failed.' }
}
New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
$ServerReady = $false
try {
    $Config = Invoke-RestMethod "$BaseUrl/api/config" -TimeoutSec 2
    $ServerReady = $null -ne $Config.streams -and $null -ne $Config.policy
} catch { }

if (-not $ServerReady) {
    $ServerProcess = Start-Process -FilePath $VisionPython `
        -ArgumentList @('-X', 'utf8', '-u', '-m', 'backend.server', '--port', "$Port") `
        -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $OutputFolder 'windows-server.log') `
        -RedirectStandardError (Join-Path $OutputFolder 'windows-server-error.log')
    for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
        if ($ServerProcess.HasExited) {
            throw "Server exited. See $OutputFolder\windows-server-error.log"
        }
        try {
            $Config = Invoke-RestMethod "$BaseUrl/api/config" -TimeoutSec 2
            if ($null -ne $Config.streams -and $null -ne $Config.policy) {
                $ServerReady = $true
                break
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ServerReady) { throw 'Server did not become ready; inspect run-output/windows-server-error.log.' }
    Write-Host "Local server PID: $($ServerProcess.Id)"
}
Write-Host "Video analysis: $BaseUrl/sources.html"
Write-Host "Python: $VisionPython"
Write-Host 'Windows uses CPU; the original macOS environment and paths are preserved.'
if (-not $NoBrowser) { Start-Process "$BaseUrl/sources.html" }
