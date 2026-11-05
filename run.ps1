$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvActivate = Join-Path $ScriptDir "venv\Scripts\Activate.ps1"

if (Test-Path $VenvActivate) {
    Set-Location $ScriptDir
    & $VenvActivate
    python server/run_assistant.py @args
} else {
    Write-Host "[ERROR] Virtual environment not found at $VenvActivate" -ForegroundColor Red
}
