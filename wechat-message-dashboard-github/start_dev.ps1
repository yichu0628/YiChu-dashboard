# WeChat message board module - unified startup script (Windows)
# Creates/reuses venv (prefer py launcher), then runs run.py.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path "$root\venv\Scripts\python.exe")) {
    Write-Host "==> Creating venv ..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv "$root\venv"
    } else {
        python -m venv "$root\venv"
    }
}

& "$root\venv\Scripts\python.exe" "$root\run.py" @args