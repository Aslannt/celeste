$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "[Celeste] Creando entorno virtual..."
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "[Celeste] Instalando/actualizando dependencias..."
& $Python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $env:CELESTE_API_TOKEN -and -not (Test-Path ".env")) {
    Write-Warning "No existe .env ni CELESTE_API_TOKEN. Se usara el token de desarrollo. Solo para pruebas en tu LAN."
}

Write-Host "[Celeste] Iniciando Core en http://0.0.0.0:8000"
Write-Host "[Celeste] Swagger local: http://127.0.0.1:8000/docs"
& $Python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
exit $LASTEXITCODE
