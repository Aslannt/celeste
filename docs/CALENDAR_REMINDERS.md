# Calendar y recordatorios en Celeste

## Objetivo

Celeste distingue entre tres conceptos:

1. **Notas/tareas de Brain**: informacion durable, pero sin garantia de aviso futuro.
2. **Recordatorios locales**: acciones one-shot programadas por Celeste Core que generan una notificacion cuando vence la hora.
3. **Eventos de Google Calendar**: agenda externa sincronizada mediante la API oficial de Google Calendar.

Una nota que contiene palabras como `manana`, `sabado` o `recordatorio` no se considera programada. Celeste solo puede afirmar que existe un aviso futuro cuando `create_reminder` o una operacion Calendar devuelve `status=executed`.

## Recordatorios locales

Se almacenan en:

```text
CelesteBrain/.celeste/reminders.json
```

El archivo contiene solo datos de recordatorios y permanece bajo control local. `ReminderStore` usa escritura temporal + reemplazo atomico para reducir el riesgo de corrupcion.

Herramientas:

- `list_reminders` -> READ
- `create_reminder` -> SAFE_WRITE
- `complete_reminder` -> SAFE_WRITE
- `cancel_reminder` -> CONFIRM

El monitor de Core revisa recordatorios pendientes cada `CELESTE_REMINDER_POLL_SECONDS` (30 segundos por defecto). Cuando un recordatorio vence crea una entrada deduplicada en el NotificationStore y marca el recordatorio como disparado.

La primera version soporta recordatorios one-shot. Recurrencia se anadira solo despues de validar el flujo basico en el PC y telefono reales.

## Google Calendar

Celeste usa Google Calendar API v3 con OAuth Desktop local. Las credenciales y tokens nunca se envian al modelo ni a Android.

Archivos locales por defecto:

```text
celeste-core/.secrets/calendar-credentials.json
celeste-core/.secrets/calendar-token.json
```

Variables:

```text
CELESTE_CALENDAR_ENABLED=false
CELESTE_CALENDAR_CREDENTIALS_FILE=<opcional>
CELESTE_CALENDAR_TOKEN_FILE=<opcional>
CELESTE_CALENDAR_ID=primary
CELESTE_CALENDAR_TIME_ZONE=America/Bogota
CELESTE_REMINDER_POLL_SECONDS=30
```

Scope solicitado:

```text
https://www.googleapis.com/auth/calendar.events
```

Herramientas:

- `calendar_list_events` -> READ
- `calendar_get_event` -> READ
- `calendar_create_event` -> SAFE_WRITE
- `calendar_update_event` -> CONFIRM
- `calendar_delete_event` -> CONFIRM

La creacion de eventos de esta fase no admite asistentes y usa `sendUpdates=none`; por tanto Celeste no envia invitaciones a terceros. Modificar o eliminar eventos existentes requiere CONFIRM.

Todo contenido recuperado de Calendar se marca `untrusted_external_content=true`, porque titulo, descripcion, ubicacion o asistentes pueden venir de terceros. La IA debe tratar ese contenido como datos, nunca instrucciones.

## Reloj y expresiones relativas

Cuando el Tool Router expone capacidades de scheduling, el schema entregado al proveedor incluye la fecha/hora local actual y `CELESTE_CALENDAR_TIME_ZONE`. Esto permite convertir peticiones como:

```text
Recuérdame mañana a las 8 comprar leche.
```

a una fecha ISO-8601 explicita sin que el modelo tenga que adivinar el dia actual.

## Autorizacion local de Calendar

1. Habilitar Google Calendar API en el mismo proyecto Google Cloud usado por Celeste o en un proyecto dedicado.
2. Crear/usar un OAuth Client de tipo Desktop.
3. Descargar el JSON de credenciales a `.secrets/calendar-credentials.json`.
4. Establecer `CELESTE_CALENDAR_ENABLED=true` en `.env`.
5. Ejecutar desde `celeste-core`:

```powershell
.\connect_calendar_windows.ps1
```

El navegador abre el consentimiento de Google. Celeste nunca solicita ni almacena la contrasena de Google.

## Validacion antes de merge

- CI Core + Android verde.
- `GET /api/v1/integrations/calendar/status` autorizado.
- listar eventos reales sin modificar nada.
- crear un evento inocuo sin asistentes.
- pedir update, comprobar `confirmation_required`, cancelar y verificar que no cambia.
- pedir delete, confirmar y verificar eliminacion.
- crear un recordatorio de prueba a pocos minutos, esperar la notificacion y comprobar deduplicacion.
- probar intents naturales con `qwen3.5:9b`.
