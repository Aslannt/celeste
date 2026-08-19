# Celeste Android V0.4.0

Cliente Android de Celeste para control del PC, memoria personal y conversacion con Celeste Core.

## Incluye

- Estado de Celeste Core por LAN.
- Wake-on-LAN.
- Crear y listar notas en Celeste Brain.
- Busqueda de notas por titulo, contenido y tags mediante SQLite FTS5.
- Tarjeta `Hablar con Celeste` conectada al nuevo endpoint del asistente.
- Visualizacion del proveedor usado y de las herramientas ejecutadas.
- Configuracion local persistente.
- Cola offline de notas con Room.
- Sincronizacion inmediata si Core esta disponible.
- Reintento automatico de notas pendientes mientras la app esta activa.
- Sincronizacion idempotente para evitar notas duplicadas en reintentos.

## Asistente V0.4

La app envia el mensaje a:

```text
POST /api/v1/assistant/chat
```

Celeste Core selecciona el proveedor configurado y todas las capacidades pasan por el Tool Router. Android no entrega acceso directo al sistema ni al Brain al proveedor de IA.

Con el proveedor por defecto `local_rules` puedes probar sin Internet ni clave externa:

```text
Busca moto
Recuerda que comprar filtro de aceite
Cual es el estado del PC?
```

Cuando Core se configure con un LLM real, la misma interfaz podra interpretar lenguaje mucho mas libre sin cambiar las herramientas reales disponibles.

## Busqueda y notas

Markdown sigue siendo la fuente de verdad. El indice SQLite FTS5 es reconstruible y se mantiene sincronizado cuando se crean, editan o eliminan logicamente notas.

Al guardar una nota manual desde Android, se escribe primero en la cola Room. Si Core esta disponible se sincroniza inmediatamente; si no, permanece pendiente hasta que Core vuelva.

## Configuracion inicial

En la app introduce:

- URL de Core: `http://<IP_DEL_PC>:8000`
- API token: el mismo token privado configurado en Celeste Core.
- MAC del adaptador Ethernet del PC.
- Broadcast de tu red, por ejemplo `192.168.1.255`.
- Puerto WOL: `9`.

La app usa HTTP sin cifrar solo para pruebas dentro de la LAN. No expongas Celeste Core a Internet con esta configuracion.

## Prueba V0.4

1. Ejecuta los tests de Core.
2. Arranca Core 0.4.0 con `CELESTE_LLM_PROVIDER=local_rules`.
3. Instala Android 0.4.0.
4. En `Hablar con Celeste`, prueba `Busca moto` y confirma que usa `search_memory (READ)`.
5. Prueba `Recuerda que ...` y confirma que usa `create_note (SAFE_WRITE)` y aparece un Markdown nuevo.
6. Prueba `Cual es el estado del PC?` y confirma que usa `get_pc_status (READ)`.
7. Solo despues de validar lo anterior, configura un proveedor LLM real y repite las pruebas con lenguaje natural.
