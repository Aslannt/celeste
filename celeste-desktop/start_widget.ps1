# Arranca el orbe de Celeste sin consola. Uso: .\start_widget.ps1
# Con -Install crea un acceso directo en Inicio de Windows para que arranque solo.
param([switch]$Install)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $here ".venv\Scripts\pythonw.exe"
$app = Join-Path $here "app.py"
if ($Install) {
    $startup = [Environment]::GetFolderPath("Startup")
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path $startup "Celeste.lnk"))
    $link.TargetPath = $pythonw
    $link.Arguments = "`"$app`""
    $link.WorkingDirectory = $here
    $link.Save()
    Write-Host "Celeste arrancara sola al iniciar sesion."
}
Start-Process -FilePath $pythonw -ArgumentList "`"$app`"" -WorkingDirectory $here
