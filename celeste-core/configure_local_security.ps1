param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$EnvFile = Join-Path $PSScriptRoot ".env"

if ((Test-Path $EnvFile) -and -not $Force) {
    Write-Host "[Celeste] Ya existe .env. No se modifico. Usa -Force si deseas regenerar el token."
    $Existing = Get-Content $EnvFile | Where-Object { $_ -match '^CELESTE_API_TOKEN=' } | Select-Object -First 1
    if ($Existing) {
        $Token = $Existing.Substring("CELESTE_API_TOKEN=".Length)
        Write-Host "[Celeste] Token actual para configurar Android:"
        Write-Host $Token
    }
    exit 0
}

$Bytes = New-Object byte[] 32
$Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $Rng.GetBytes($Bytes)
} finally {
    $Rng.Dispose()
}

$Token = [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')

@(
    "CELESTE_API_TOKEN=$Token"
    "# Optional. If omitted, CelesteBrain is created next to the repository root."
    "# CELESTE_BRAIN_DIR=D:\\CelesteBrain"
) | Set-Content -Path $EnvFile -Encoding ascii

Write-Host "[Celeste] Configuracion privada creada en: $EnvFile"
Write-Host "[Celeste] Copia este token en Celeste Android -> API token:"
Write-Host $Token
Write-Host "[Celeste] .env esta ignorado por Git y no debe compartirse ni subirse al repositorio."
