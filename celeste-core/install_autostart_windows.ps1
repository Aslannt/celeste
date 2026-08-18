$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$TaskName = "Celeste Core"
$StartScript = Join-Path $PSScriptRoot "start_windows.ps1"
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "No existe el entorno virtual. Ejecuta run_windows.ps1 una vez y detenlo con Ctrl+C antes de instalar el autoarranque."
}

if (-not (Test-Path (Join-Path $PSScriptRoot ".env"))) {
    Write-Warning "No existe .env. Ejecuta configure_local_security.ps1 antes de instalar el autoarranque para no usar el token de desarrollo."
}

$PowerShell = (Get-Command powershell.exe).Source
$Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`""

$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Starts Celeste Core automatically when the current Windows user signs in." `
    -Force | Out-Null

Write-Host "[Celeste] Autoarranque instalado: $TaskName"
Write-Host "[Celeste] Puedes probarlo ahora con: Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "[Celeste] Estado: Get-ScheduledTask -TaskName `"$TaskName`""
