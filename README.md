# Celeste

Celeste es un asistente personal distribuido en construccion. La arquitectura actual usa **Celeste Core** en el PC, **Celeste Android** como cliente y **Celeste Brain** como memoria abierta basada en Markdown.

## Estado actual

- Wake-on-LAN desde Celeste Android.
- Celeste Core con FastAPI en Windows/Fedora.
- Autoarranque de Core en Windows al iniciar sesion.
- Token local privado para la API.
- Celeste Brain con notas Markdown + YAML frontmatter.
- Notas offline en Android con Room y sincronizacion idempotente.
- V0.3: indice SQLite + FTS5 reconstruible y busqueda desde Android.
- IA, voz, Home Assistant y servidor 24/7 siguen fuera del alcance actual.

## Principio de Celeste Brain

Los archivos Markdown son la fuente de verdad. El indice SQLite vive en:

```text
CelesteBrain/.celeste/brain-index.sqlite3
```

Ese archivo es cache reconstruible: puede borrarse y Celeste Core lo vuelve a generar desde `CelesteBrain/notes` al arrancar.

## Estructura

```text
celeste/
├── celeste-core/       # API local, Brain index y servicios
├── celeste-android/    # cliente Android, WOL y memoria offline
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
```

Swagger esta disponible en `http://127.0.0.1:8000/docs`.

Las operaciones de notas requieren `X-Celeste-Token`. Usa `configure_local_security.ps1` para crear la configuracion privada local en `.env`; no subas ese archivo al repositorio.

## Siguiente etapa

Despues de validar V0.3 en el PC y telefono reales, el siguiente bloque es la abstraccion de proveedores de IA y el Tool Router. La busqueda lexical FTS5 sera la primera implementacion de `search_memory`; embeddings/RAG se evaluaran mas adelante y no reemplazaran Markdown como fuente de verdad.
