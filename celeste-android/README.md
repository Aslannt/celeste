# Celeste Android V0.2

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

## Notas offline

Al guardar una nota, Celeste la escribe primero en la base de datos Room del telefono.

- Si Celeste Core esta disponible, la nota se envia al Core y se elimina de la cola local despues de recibir una respuesta exitosa.
- Si el PC/Core esta apagado o no se puede alcanzar, la nota permanece en `Pendientes de sincronizar`.
- Cuando Core vuelve, la app reintenta y la nota termina en `CelesteBrain/notes` como Markdown.

Esta V0.2 usa una cola de entrega al menos una vez: prioriza no perder contenido. Una interrupcion exactamente despues de que Core cree una nota pero antes de que Android reciba la respuesta podria producir un duplicado. La idempotencia se implementara en una iteracion posterior si hace falta.

La V0.2 todavia no cachea en Room todas las notas remotas ni hace sincronizacion bidireccional/conflictos. Room se usa solamente como cola durable para nuevas notas creadas desde Android.

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

## Prueba V0.2

1. Con Core online, guarda una nota y confirma que aparece inmediatamente en Celeste Brain.
2. Apaga completamente el PC.
3. Guarda una nota nueva desde Android y confirma que aparece en `Pendientes de sincronizar`.
4. Cierra y vuelve a abrir la app para comprobar que la pendiente sigue presente.
5. Enciende el PC con Wake-on-LAN desde Celeste.
6. Cuando Core arranque automaticamente, deja Celeste Android abierta o pulsa `Actualizar`.
7. Confirma que desaparece de pendientes y aparece en las notas remotas y en `CelesteBrain/notes`.
