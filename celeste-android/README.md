# Celeste Android V0.3.0

Cliente Android de Celeste para control del PC y memoria personal.

## Incluye

- Estado de Celeste Core por LAN.
- Wake-on-LAN.
- Crear y listar notas en Celeste Brain.
- Busqueda de notas por titulo, contenido y tags mediante el indice FTS5 del Core.
- Configuracion local persistente.
- Cola offline de notas con Room.
- Sincronizacion inmediata si Core esta disponible.
- Reintento automatico de notas pendientes mientras la app esta activa.
- Reintento al abrir la app y al pulsar `Actualizar`.
- Sincronizacion idempotente para evitar notas duplicadas en reintentos.

## Busqueda V0.3

La app incluye la tarjeta `Buscar en Celeste Brain`. La busqueda se ejecuta en Celeste Core contra un indice SQLite FTS5 reconstruible.

Markdown sigue siendo la fuente de verdad. Android recibe como resultado las notas originales leidas nuevamente desde sus archivos Markdown.

La busqueda V0.3 requiere que Core este en linea. El cache offline completo y la busqueda local en Android quedan fuera de este incremento.

## Notas offline

Al guardar una nota, Celeste la escribe primero en la base de datos Room del telefono.

- Si Celeste Core esta disponible, la nota se envia al Core y se elimina de la cola local despues de recibir una respuesta exitosa.
- Si el PC/Core esta apagado o no se puede alcanzar, la nota permanece en `Pendientes de sincronizar`.
- Cuando Core vuelve, la app reintenta y la nota termina en `CelesteBrain/notes` como Markdown.

## Idempotencia

Cada nota pendiente tiene un `localId` UUID generado una sola vez en Android. Ese mismo valor se reutiliza como `X-Celeste-Idempotency-Key` en cada intento de sincronizacion.

Celeste Core guarda la clave en el frontmatter Markdown. Si recibe el mismo intento otra vez con el mismo contenido, devuelve la nota existente en vez de crear un segundo archivo. Si una clave ya usada llega con contenido distinto, Core responde HTTP 409.

Room todavia no cachea todas las notas remotas ni hace sincronizacion bidireccional/conflictos. Se usa como cola durable para nuevas notas creadas desde Android.

## Configuracion inicial

En la app introduce:

- URL de Core: `http://<IP_DEL_PC>:8000`
- API token: el mismo token privado configurado en Celeste Core.
- MAC del adaptador Ethernet del PC.
- Broadcast de tu red, por ejemplo `192.168.1.255`.
- Puerto WOL: `9`.

La app usa HTTP sin cifrar solo para pruebas dentro de la LAN. No expongas Celeste Core a Internet con esta configuracion.

## Prueba V0.3

1. Ejecuta los tests de Core y confirma que FTS5 funciona.
2. Compila Android V0.3.0 e instalalo sobre la version actual.
3. Arranca Core y pulsa `Actualizar` en Android.
4. Busca una palabra que exista en el titulo o contenido de una nota conocida.
5. Busca un tag conocido.
6. Confirma que una nota nueva aparece en busqueda inmediatamente despues de sincronizarse.
