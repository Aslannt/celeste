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

V0.4 incluye dos proveedores intercambiables:

### `local_rules`

Es el valor por defecto. No usa Internet ni una API externa. Sirve para validar el flujo completo de Celeste y entiende un conjunto pequeno de intenciones explicitas, por ejemplo:

```text
Busca moto
Recuerda que comprar filtro de aceite
Cual es el estado del PC?
```

No pretende sustituir un LLM.

### `openai`

Usa la Responses API mediante el SDK oficial de OpenAI y function calling. El modelo solo puede solicitar las herramientas publicadas por `ToolRouter`.

Configuracion local en `celeste-core/.env`:

```dotenv
CELESTE_LLM_PROVIDER=openai
CELESTE_LLM_MODEL=gpt-5
OPENAI_API_KEY=tu_clave_privada
```

`OPENAI_API_KEY` es distinta de `CELESTE_API_TOKEN`. Ninguna de las dos se debe versionar.

Para volver al modo sin nube:

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

## Herramientas V0.4

- `search_memory` - READ
- `create_note` - SAFE_WRITE
- `get_pc_status` - READ

`wake_pc` se mantiene fuera del router por ahora: Celeste Core sigue ejecutandose en el mismo PC que se quiere despertar. Tendra sentido cuando exista un Core 24/7 en otro equipo o cuando el cliente Android pueda ejecutar una accion local confirmada.

## Conectores futuros

Gmail entrara como herramientas del mismo router, no como acceso especial:

- `read_email` -> READ
- `draft_email` -> SAFE_WRITE
- `send_email` -> CONFIRM

LinkedIn se evaluara por separado segun el acceso oficial disponible. Celeste no dependera de scraping de credenciales o automatizacion fragil del navegador para enviar mensajes.
