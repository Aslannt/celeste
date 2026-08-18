# Autoarranque de Celeste Core en Windows

Objetivo: que Celeste Core arranque automaticamente despues de iniciar sesion en Windows, sin abrir PowerShell manualmente.

Esta primera version usa el Programador de tareas de Windows con el usuario actual. No instala Celeste como servicio del sistema.

## 1. Crear `.env`

Dentro de `celeste-core`, copia `.env.example` a `.env` y reemplaza `CELESTE_API_TOKEN` por un token largo y aleatorio.

`.env` esta ignorado por Git y no debe subirse al repositorio.

## 2. Preparar el entorno

Ejecuta una vez:

```powershell
cd celeste-core
.\run_windows.ps1
```

Cuando Celeste Core este funcionando, detenlo con `Ctrl+C`.

## 3. Instalar autoarranque

Ejecuta:

```powershell
.\install_autostart_windows.ps1
```

Esto crea una tarea llamada `Celeste Core` que ejecuta `start_windows.ps1` al iniciar sesion.

## 4. Probar

Puedes iniciar la tarea manualmente con:

```powershell
Start-ScheduledTask -TaskName "Celeste Core"
```

Y comprobar:

```text
http://127.0.0.1:8000/api/v1/status
```

## Nota

Este mecanismo comienza despues del inicio de sesion del usuario. Mas adelante, si Celeste necesita estar disponible antes de iniciar sesion, se migrara a un servicio de Windows dedicado.
