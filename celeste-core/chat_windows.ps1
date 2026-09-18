Set-Location $PSScriptRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

$BaseUrl = "http://127.0.0.1:8000"

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$' -and $_ -notmatch '^\s*#') {
            Set-Item -Path "env:$($matches[1])" -Value $matches[2]
        }
    }
}

if (-not $env:CELESTE_API_TOKEN) {
    Write-Error "No se encontro CELESTE_API_TOKEN en .env. Corre configure_local_security.ps1 primero."
    exit 1
}

function Repair-Utf8Text($text) {
    # Windows PowerShell 5.1's Invoke-RestMethod decodes JSON responses as
    # Latin-1 when the server doesn't send an explicit charset, mangling
    # accents/enies. Reversing that mis-decode recovers the real UTF-8 text.
    if ([string]::IsNullOrEmpty($text)) { return $text }
    $latin1 = [System.Text.Encoding]::GetEncoding(28591)
    return [System.Text.Encoding]::UTF8.GetString($latin1.GetBytes($text))
}

function Test-CoreUp {
    try {
        Invoke-RestMethod -Uri $BaseUrl -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-CoreUp)) {
    Write-Host "[Celeste] Core no responde, arrancandolo en segundo plano..."
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSScriptRoot\start_windows.ps1`"" `
        -WindowStyle Hidden

    $attempts = 0
    while (-not (Test-CoreUp) -and $attempts -lt 30) {
        Start-Sleep -Seconds 1
        $attempts++
    }

    if (-not (Test-CoreUp)) {
        Write-Error "Celeste Core no arranco a tiempo. Revisa celeste-core\logs\celeste-core.log"
        exit 1
    }
}

Write-Host ""
Write-Host "Celeste esta lista. Escribe tu mensaje y Enter." -ForegroundColor Cyan
Write-Host "Comandos: 'reset' para borrar el historial de esta charla, 'salir' para terminar." -ForegroundColor DarkGray
Write-Host ""

$headers = @{ "X-Celeste-Token" = $env:CELESTE_API_TOKEN }

while ($true) {
    Write-Host "Tu: " -ForegroundColor Green -NoNewline
    $message = Read-Host

    if ([string]::IsNullOrWhiteSpace($message)) { continue }
    if ($message -in @("salir", "exit", "quit")) { break }

    if ($message -eq "reset") {
        try {
            Invoke-RestMethod -Uri "$BaseUrl/api/v1/assistant/conversation" -Method Delete -Headers $headers | Out-Null
            Write-Host "(historial borrado)" -ForegroundColor DarkGray
        } catch {
            Write-Warning "No se pudo borrar el historial: $_"
        }
        continue
    }

    try {
        $body = @{ message = $message } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$BaseUrl/api/v1/assistant/chat" `
            -Method Post -ContentType "application/json" -Headers $headers -Body $body
        Write-Host "Celeste: " -ForegroundColor Magenta -NoNewline
        Write-Host (Repair-Utf8Text $response.reply)
    } catch {
        Write-Warning "Error hablando con Celeste: $_"
    }
    Write-Host ""
}

Write-Host "Hasta luego."
