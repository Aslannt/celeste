# Celeste

Celeste es un asistente personal distribuido en construccion. Esta primera version se concentra en una base pequena y comprobable: **Celeste Core** en el PC y almacenamiento de notas Markdown abierto.

## Estado actual

- Wake-on-LAN del PC: probado correctamente desde Android.
- Celeste Core: FastAPI en Windows/Fedora.
- Celeste Brain: notas Markdown con YAML frontmatter.
- Android propio: siguiente paso.
- IA, voz, Home Assistant y servidor 24/7: deliberadamente fuera de esta version.

## Estructura

```text
celeste/
├── celeste-core/       # API local del PC
├── docs/               # decisiones y roadmap
└── CelesteBrain/       # se crea al ejecutar; datos personales, no se versiona
```

## Arranque rapido en Windows

Necesitas Python 3.12 o superior.

```powershell
cd celeste-core
.\run_windows.ps1
```

Al iniciar, abre:

- API: `http://127.0.0.1:8000/api/v1/status`
- Swagger: `http://127.0.0.1:8000/docs`

Para acceder desde el celular en la misma red usa la IP LAN del PC, por ejemplo:

```text
http://<IP_LAN_DEL_PC>:8000/api/v1/status
```

> Usa la IP privada actual de tu PC. No guardamos una IP domestica concreta en el repositorio. Mas adelante Celeste descubrira el Core automaticamente.

## Token local

Las operaciones sobre notas requieren el header:

```text
X-Celeste-Token: celeste-local-dev
```

Ese valor es solo para desarrollo. Antes de permitir acceso remoto debe cambiarse por un secreto real.

Puedes definir otro token antes de iniciar:

```powershell
$env:CELESTE_API_TOKEN="pon-aqui-un-token-largo"
.\run_windows.ps1
```

## Primer objetivo de prueba

1. Levantar Celeste Core.
2. Abrir `/api/v1/status` desde el PC.
3. Abrir el mismo endpoint desde Android usando la IP LAN del PC.
4. Crear una nota desde Swagger.
5. Confirmar que aparece como `.md` dentro de `CelesteBrain/notes/`.

Una vez eso funcione, el siguiente incremento sera `celeste-android`: boton de Wake-on-LAN + captura de notas offline.
