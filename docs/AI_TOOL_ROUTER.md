# IA y Tool Router de Celeste

## Objetivo

Celeste separa la conversacion de las capacidades reales del sistema.

Un proveedor de IA nunca recibe acceso directo al shell, al sistema de archivos ni a credenciales. Solo recibe una lista de herramientas declaradas por `ToolRouter`, y cada llamada vuelve al Core para validacion y ejecucion.

## Niveles de riesgo

- `READ`: consultas sin cambios persistentes, por ejemplo `search_memory` o `get_pc_status`.
- `SAFE_WRITE`: cambios acotados y reversibles/esperados, por ejemplo crear una nota Markdown.
- `CONFIRM`: la herramienta se bloquea hasta que el usuario confirme explicitamente la accion.
- `RESTRICTED`: no se expone al proveedor y no puede ejecutarse desde la IA.

La infraestructura de confirmacion genera un ID temporal. El handler sensible no se ejecuta antes de confirmar.

## Proveedores

Celeste soporta tres proveedores intercambiables via `CELESTE_LLM_PROVIDER`:

### `local_rules`

Es el valor por defecto. No usa Internet ni una API externa. Sirve para validar el flujo completo de Celeste y entiende un conjunto pequeno de intenciones explicitas, por ejemplo:

```text
Busca moto
Recuerda que comprar filtro de aceite
Cual es el estado del PC?
```

No pretende sustituir un LLM.

### `ollama` (recomendado para uso diario local, costo 0)

Modelo conversacional local via Ollama, sin nube y sin suscripcion. Es el proveedor recomendado para el uso diario de Celeste.

```dotenv
CELESTE_LLM_PROVIDER=ollama
CELESTE_LLM_MODEL=qwen3.5:9b
CELESTE_OLLAMA_URL=http://127.0.0.1:11434
```

Ver [ADR-006](DECISIONS.md) sobre el tamano de modelo elegido mientras el Core corre por CPU.

### `openai` (opcional, de pago)

Usa la Responses API mediante el SDK oficial de OpenAI y function calling. El modelo solo puede solicitar las herramientas publicadas por `ToolRouter`. Requiere `OPENAI_API_KEY` y consume creditos de pago: no es el default y no deberia activarse salvo necesidad puntual.

```dotenv
CELESTE_LLM_PROVIDER=openai
CELESTE_LLM_MODEL=gpt-5.6
OPENAI_API_KEY=tu_clave_privada
```

`OPENAI_API_KEY` es distinta de `CELESTE_API_TOKEN`. Ninguna de las dos se debe versionar.

Para volver al modo sin nube y costo 0:

```dotenv
CELESTE_LLM_PROVIDER=local_rules
```

## API

```text
GET  /api/v1/assistant/tools
POST /api/v1/assistant/chat
POST /api/v1/assistant/confirm/{confirmation_id}
```

Ejemplo de chat:

```json
{
  "message": "Busca en mi memoria algo sobre la moto"
}
```

La respuesta incluye texto, proveedor y eventos de herramientas. Esto permite que Android muestre que una respuesta uso `search_memory`, `create_note`, etc.

## Herramientas actuales (V0.4.2)

Brain y PC:

- `search_memory` - READ
- `create_note` - SAFE_WRITE
- `update_note` - CONFIRM
- `delete_note` - CONFIRM
- `get_pc_status` - READ

Recordatorios locales:

- `list_reminders` - READ
- `create_reminder` - SAFE_WRITE
- `complete_reminder` - SAFE_WRITE
- `cancel_reminder` - CONFIRM

Gmail (contenido marcado como no confiable, ver regla dura 4 de `CLAUDE.md`):

- `gmail_list_unread` - READ
- `gmail_search` - READ
- `gmail_read_message` - READ
- `gmail_create_draft` - SAFE_WRITE
- `gmail_create_reply_draft` - SAFE_WRITE
- `gmail_send_draft` - CONFIRM (protegido ademas por el send guard de huella del RAW)

Google Calendar (contenido marcado como no confiable):

- `calendar_list_events` - READ
- `calendar_get_event` - READ
- `calendar_create_event` - SAFE_WRITE (sin asistentes)
- `calendar_update_event` - CONFIRM
- `calendar_delete_event` - CONFIRM

`wake_pc` se mantiene fuera del router por ahora: Celeste Core sigue ejecutandose en el mismo PC que se quiere despertar. Tendra sentido cuando exista un Core 24/7 en otro equipo o cuando el cliente Android pueda ejecutar una accion local confirmada.

## Conectores futuros

LinkedIn se evaluara por separado segun el acceso oficial disponible. Celeste no dependera de scraping de credenciales o automatizacion fragil del navegador para enviar mensajes.
