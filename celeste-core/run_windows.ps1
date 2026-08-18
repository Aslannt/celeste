$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "[Celeste] Creando entorno virtual..."
    py -3 -m venv .venv
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "[Celeste] Instalando/actualizando dependencias..."
& $Python -m pip install -e ".[dev]"

if (-not $env:CELESTE_API_TOKEN) {
    $env:CELESTE_API_TOKEN = "celeste-local-dev"
    Write-Warning "Usando token de desarrollo. Solo para pruebas en tu LAN."
}

Write-Host "[Celeste] Iniciando Core en http://0.0.0.0:8000"
Write-Host "[Celeste] Swagger local: http://127.0.0.1:8000/docs"
& $Python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
