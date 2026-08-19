# Celeste

Celeste es un asistente personal distribuido en construccion. La arquitectura actual usa **Celeste Core** en el PC, **Celeste Android** como cliente y **Celeste Brain** como memoria abierta basada en Markdown.

## Estado actual

- Wake-on-LAN desde Celeste Android.
- Celeste Core con FastAPI en Windows/Fedora.
- Autoarranque de Core en Windows al iniciar sesion.
- Token local privado para la API.
- Celeste Brain con notas Markdown + YAML frontmatter.
- Notas offline en Android con Room y sincronizacion idempotente.
- Indice SQLite + FTS5 reconstruible y busqueda desde Android.
- V0.4 en desarrollo: proveedor de IA intercambiable + Tool Router con permisos.
- Voz, Home Assistant y servidor 24/7 siguen en fases posteriores.

## Principio de Celeste Brain

Los archivos Markdown son la fuente de verdad. El indice SQLite vive en:

```text
CelesteBrain/.celeste/brain-index.sqlite3
```

Ese archivo es cache reconstruible: puede borrarse y Celeste Core lo vuelve a generar desde `CelesteBrain/notes` al arrancar.

## IA y herramientas

Celeste no entrega acceso directo al sistema a un LLM. Los proveedores solo pueden solicitar herramientas registradas por el Tool Router, clasificadas como:

```text
READ / SAFE_WRITE / CONFIRM / RESTRICTED
```

V0.4 incluye inicialmente:

```text
search_memory   READ
create_note     SAFE_WRITE
get_pc_status   READ
```

El proveedor por defecto es `local_rules`, que permite probar todo sin Internet ni una API externa. El proveedor `openai` se habilita localmente mediante variables en `celeste-core/.env`; las claves nunca se versionan. Consulta `docs/AI_TOOL_ROUTER.md`.

## Estructura

```text
celeste/
├── celeste-core/       # API local, Brain, Tool Router y proveedores de IA
├── celeste-android/    # cliente Android, WOL, memoria offline y chat
├── docs/               # decisiones, arquitectura y roadmap
└── CelesteBrain/       # datos personales; no se versiona
```

## Arranque en Windows

Necesitas Python 3.12 o superior.

```powershell
cd celeste-core
.\run_windows.ps1
```

Servicios locales principales:

```text
GET  /api/v1/status
GET  /api/v1/notes
POST /api/v1/notes
GET  /api/v1/notes/search?q=<texto>
POST /api/v1/notes/index/rebuild
GET  /api/v1/assistant/tools
POST /api/v1/assistant/chat
POST /api/v1/assistant/confirm/{confirmation_id}
```

Swagger esta disponible en `http://127.0.0.1:8000/docs`.

Las operaciones privadas requieren `X-Celeste-Token`. Usa `configure_local_security.ps1` para crear la configuracion privada local en `.env`; no subas ese archivo al repositorio.

## Conectores siguientes

Despues de validar V0.4, Gmail sera el primer conector externo: lectura, resumen, borradores y envio solo despues de confirmacion. LinkedIn se evaluara segun el acceso oficial disponible para mensajeria, evitando scraping o automatizacion fragil del navegador.
