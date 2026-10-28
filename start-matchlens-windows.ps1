param(
    [ValidateRange(1024, 65535)][int]$Port = 43128,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$OutputFolder = Join-Path $ProjectRoot 'run-output'
$BaseUrl = "http://127.0.0.1:$Port"
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$ServerReady = $false
try {
    $Config = Invoke-RestMethod "$BaseUrl/api/config" -TimeoutSec 2
    $ServerReady = $null -ne $Config.streams -and $null -ne $Config.policy
} catch { }

if (-not $ServerReady) {
    $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
    $PythonArguments = @('-3.13')
    if ($null -eq $PythonCommand) {
        $PythonCommand = Get-Command python -ErrorAction Stop
        $PythonArguments = @()
    }
    New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
    $PythonArguments += @('-X', 'utf8', '-u', '-m', 'backend.server', '--port', "$Port")
    $ServerProcess = Start-Process -FilePath $PythonCommand.Source `
        -ArgumentList $PythonArguments -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru `
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

$StadiumUrl = "http://127.0.0.1:$Port/"
Write-Host "Animated stadium (Fan / Coach / Commentator): $StadiumUrl"
Write-Host 'Optional video inference has a separate launcher: start-video-windows.ps1'
if (-not $NoBrowser) { Start-Process $StadiumUrl }
