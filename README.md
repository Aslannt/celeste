# Celeste

Celeste es un asistente personal distribuido, de uso personal. La arquitectura usa **Celeste Core** (API local en FastAPI) en el PC, **Celeste Android** como cliente movil, un **cliente web** servido por el propio Core, y **Celeste Brain** como memoria abierta basada en Markdown.

## Estado actual

- Celeste Core con FastAPI, autoarranque en Windows y token local privado para la API.
- Celeste Brain con notas Markdown + YAML frontmatter; indice SQLite + FTS5 reconstruible.
- Tool Router con niveles READ / SAFE_WRITE / CONFIRM / RESTRICTED; auditoria local sin guardar contenido privado.
- Proveedores de IA intercambiables: `local_rules` (sin red), `ollama` (local, recomendado, costo 0) y `openai` (opcional, de pago).
- Memoria de conversacion de corto plazo entre turnos (se resetea a los 30 min de inactividad).
- Gmail (lectura, borradores, envio con confirmacion) y Google Calendar (lectura y CRUD con confirmacion) via OAuth local.
- Recordatorios locales durables (crear, actualizar, completar, cancelar) con monitor y notificaciones.
- Cliente Android: Wake-on-LAN, notas offline con Room, chat con voz (STT/TTS nativo), notificaciones reales del sistema para recordatorios.
- Cliente web (`/ui` servido por Core): interfaz de voz/texto con orbe animado, funciona desde cualquier navegador de la LAN sin instalar nada, con anuncios y resumen proactivos.
- Telemetria real de PC (CPU/RAM/disco) via `get_pc_status`.
- LinkedIn Messaging evaluado y bloqueado por falta de acceso oficial gratuito (ver `docs/DECISIONS.md`).
- Voz en moto, Home Assistant y servidor 24/7 siguen en fases posteriores (ver `docs/ROADMAP.md`).

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

El proveedor por defecto es `local_rules`, que permite probar todo sin Internet ni una API externa. `ollama` corre un modelo local (recomendado para uso diario, costo 0). `openai` se habilita localmente mediante variables en `celeste-core/.env`; las claves nunca se versionan. El catalogo completo de herramientas (Brain, recordatorios, Gmail, Calendar) esta en `docs/AI_TOOL_ROUTER.md`.

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
GET    /api/v1/status
GET    /api/v1/notes
POST   /api/v1/notes
GET    /api/v1/notes/search?q=<texto>
POST   /api/v1/notes/index/rebuild
GET    /api/v1/assistant/tools
POST   /api/v1/assistant/chat
POST   /api/v1/assistant/confirm/{confirmation_id}
DELETE /api/v1/assistant/confirm/{confirmation_id}
DELETE /api/v1/assistant/conversation
GET    /api/v1/reminders
POST   /api/v1/reminders
PUT    /api/v1/reminders/{reminder_id}
GET    /api/v1/notifications
GET    /api/v1/integrations/gmail/status
GET    /api/v1/integrations/calendar/status
```

Swagger esta disponible en `http://127.0.0.1:8000/docs`. La interfaz web (voz/texto, sin instalar nada) esta en `http://127.0.0.1:8000/ui/`.

Las operaciones privadas requieren `X-Celeste-Token`. Usa `configure_local_security.ps1` para crear la configuracion privada local en `.env`; no subas ese archivo al repositorio.

## Conectores

Gmail y Google Calendar ya son conectores integrados via OAuth local (ver `docs/GMAIL_SETUP.md` y `docs/CALENDAR_REMINDERS.md`). LinkedIn se evaluo y quedo bloqueado por falta de acceso oficial gratuito para mensajeria personal (ver ADR-007 en `docs/DECISIONS.md`); no se usa scraping ni automatizacion fragil del navegador.
