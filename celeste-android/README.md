# Celeste Android V0.1

Cliente Android inicial de Celeste.

## Incluye

- Estado de Celeste Core por LAN.
- Wake-on-LAN.
- Crear notas en Celeste Brain.
- Listar notas recientes.
- Configuracion local persistente.

## Configuracion inicial

En la app introduce:

- URL de Core: `http://<IP_DEL_PC>:8000`
- API token: el mismo que use Celeste Core (en desarrollo: `celeste-local-dev`)
- MAC del adaptador Ethernet del PC.
- Broadcast de tu red, por ejemplo `192.168.1.255`.
- Puerto WOL: `9`.

La app usa HTTP sin cifrar solo para pruebas dentro de la LAN. No expongas Celeste Core a Internet con esta configuracion.

## Abrir en Android Studio

Abre esta carpeta (`celeste-android`) como proyecto Gradle, deja que Android Studio sincronice dependencias y ejecuta en un telefono conectado a la misma Wi-Fi que el PC.
