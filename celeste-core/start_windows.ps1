$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "No existe el entorno virtual. Ejecuta run_windows.ps1 una vez antes de instalar el autoarranque."
}

$LogDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$MainLog = Join-Path $LogDir "celeste-core.log"
$StdOutLog = Join-Path $LogDir "uvicorn.out.log"
$StdErrLog = Join-Path $LogDir "uvicorn.err.log"

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $MainLog -Value "[$Timestamp] Starting Celeste Core"

# Start-Process is more reliable than PowerShell stream redirection when this
# script is launched by Task Scheduler with no interactive console attached.
try {
    Remove-Item $StdOutLog, $StdErrLog -ErrorAction SilentlyContinue

    $Arguments = @(
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000"
    )

    $Process = Start-Process `
        -FilePath $Python `
        -ArgumentList $Arguments `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdOutLog `
        -RedirectStandardError $StdErrLog `
        -PassThru

    Add-Content -Path $MainLog -Value "[$Timestamp] Uvicorn PID: $($Process.Id)"

    Wait-Process -Id $Process.Id
    $Process.Refresh()

    $Finished = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $MainLog -Value "[$Finished] Uvicorn exited with code $($Process.ExitCode)"
    exit $Process.ExitCode
}
catch {
    $Failed = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $MainLog -Value "[$Failed] ERROR: $($_.Exception.Message)"
    throw
}
