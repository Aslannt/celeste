# Celeste Android V0.2.1

Cliente Android de Celeste para control del PC y memoria personal.

## Incluye

- Estado de Celeste Core por LAN.
- Wake-on-LAN.
- Crear y listar notas en Celeste Brain.
- Configuracion local persistente.
- Cola offline de notas con Room.
- Sincronizacion inmediata si Core esta disponible.
- Reintento automatico de notas pendientes mientras la app esta activa.
- Reintento al abrir la app y al pulsar `Actualizar`.
- Sincronizacion idempotente para evitar notas duplicadas en reintentos.

## Notas offline

Al guardar una nota, Celeste la escribe primero en la base de datos Room del telefono.

- Si Celeste Core esta disponible, la nota se envia al Core y se elimina de la cola local despues de recibir una respuesta exitosa.
- Si el PC/Core esta apagado o no se puede alcanzar, la nota permanece en `Pendientes de sincronizar`.
- Cuando Core vuelve, la app reintenta y la nota termina en `CelesteBrain/notes` como Markdown.

## Idempotencia V0.2.1

Cada nota pendiente tiene un `localId` UUID generado una sola vez en Android. Ese mismo valor se reutiliza como `X-Celeste-Idempotency-Key` en cada intento de sincronizacion.

Celeste Core guarda la clave en el frontmatter Markdown. Si recibe el mismo intento otra vez con el mismo contenido, devuelve la nota existente en vez de crear un segundo archivo. Si una clave ya usada llega con contenido distinto, Core responde HTTP 409.

La V0.2.1 todavia no cachea en Room todas las notas remotas ni hace sincronizacion bidireccional/conflictos. Room se usa solamente como cola durable para nuevas notas creadas desde Android.

## Configuracion inicial

En la app introduce:

- URL de Core: `http://<IP_DEL_PC>:8000`
- API token: el mismo token privado configurado en Celeste Core.
- MAC del adaptador Ethernet del PC.
- Broadcast de tu red, por ejemplo `192.168.1.255`.
- Puerto WOL: `9`.

La app usa HTTP sin cifrar solo para pruebas dentro de la LAN. No expongas Celeste Core a Internet con esta configuracion.

## Abrir en Android Studio

Abre esta carpeta (`celeste-android`) como proyecto Gradle, deja que Android Studio sincronice dependencias y ejecuta en un telefono conectado a la misma Wi-Fi que el PC.

## Prueba V0.2.1

1. Ejecuta los tests de Core y confirma que pasan los casos de idempotencia.
2. Compila e instala Android V0.2.1 sobre la version actual.
3. Verifica que una nota online sigue llegando a Celeste Brain.
4. Apaga el PC y crea una nota offline.
5. Cierra y abre la app y confirma que la nota sigue pendiente.
6. Enciende el PC por Wake-on-LAN y deja que la nota se sincronice.
7. Confirma que solo existe un archivo Markdown para esa nota.

La proteccion especifica contra reintentos duplicados tambien esta cubierta por tests automatizados de Celeste Core.
