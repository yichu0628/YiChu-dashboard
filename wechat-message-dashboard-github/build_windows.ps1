$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildVenv = Join-Path $ProjectDir ".build-venv"
$Python = Join-Path $BuildVenv "Scripts\python.exe"
$ExeName = (-join ([char[]](0x5FAE, 0x4FE1, 0x6D88, 0x606F, 0x770B, 0x677F))) + "-v1.0.1"
$SrcDir = Join-Path $ProjectDir "src"
$Template = Join-Path $SrcDir "board_template.html"

if (-not (Test-Path $Python)) {
    py -3 -m venv $BuildVenv
}

& $Python -m pip install --disable-pip-version-check -r (Join-Path $ProjectDir "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Failed to install build dependencies (exit code $LASTEXITCODE)" }
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $ExeName `
    --paths $SrcDir `
    --hidden-import gen_data `
    --hidden-import build_board `
    --hidden-import sqlite3 `
    --add-data ($Template + ";src") `
    (Join-Path $ProjectDir "desktop_app.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed (exit code $LASTEXITCODE)" }

Write-Host ("Build complete: " + (Join-Path $ProjectDir ("dist\" + $ExeName + ".exe")))
