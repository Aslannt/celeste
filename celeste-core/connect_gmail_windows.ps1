$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $Python -m pip install -e "."
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python .\connect_gmail.py
exit $LASTEXITCODE
