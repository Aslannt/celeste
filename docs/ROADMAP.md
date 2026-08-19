# Roadmap de Celeste

## Fase 0 - hardware y red

- [x] Detectar Realtek PCIe GbE Family Controller
- [x] Obtener MAC del PC
- [x] Activar Wake on Magic Packet en Windows
- [x] Desactivar Inicio rapido
- [x] Mantener ErP desactivado
- [x] Activar Power On By PCI-E en UEFI
- [x] Encender el PC desde apagado completo usando Android

## V0.1 - fundamentos

- [x] Crear esqueleto `celeste-core`
- [x] Crear `GET /api/v1/status`
- [x] Crear almacenamiento Markdown para notas
- [x] Crear CRUD basico de notas
- [x] Agregar pruebas automaticas del Core
- [x] Ejecutar Celeste Core en el PC real
- [x] Probar `/status` desde Android en LAN
- [x] Crear una nota real desde Swagger
- [x] Crear proyecto `celeste-android`
- [x] Reemplazar Wolow con boton WOL propio
- [x] Configurar token privado local
- [x] Autoarrancar Celeste Core al iniciar sesion en Windows
- [x] Guardar notas offline en Android con Room
- [x] Sincronizar notas pendientes Android -> PC
- [x] Validar sincronizacion idempotente Android -> Core

## V0.3 - Brain indexado

- [x] Mantener Markdown como fuente de verdad
- [x] Crear indice reconstruible SQLite + FTS5
- [x] Reconstruir indice al arrancar Core
- [x] Mantener indice sincronizado con CRUD de notas
- [x] Crear `GET /api/v1/notes/search`
- [x] Agregar buscador en Celeste Android
- [x] Validar FTS5 y busqueda en el PC y telefono reales

## V0.4 - IA y Tool Router

- [x] Abstraccion de proveedores (`local_rules` / `openai`)
- [x] Tool Router con niveles READ / SAFE_WRITE / CONFIRM / RESTRICTED
- [x] `create_note`
- [x] `search_memory`
- [x] `get_pc_status`
- [x] Infraestructura generica de confirmaciones
- [x] Endpoint `POST /api/v1/assistant/chat`
- [x] Interfaz Android para hablar con Celeste
- [ ] Validar proveedor local y herramientas en PC/Android reales
- [ ] Configurar y validar un proveedor LLM real
- [ ] `wake_pc` como herramienta cuando Core pueda ejecutarse fuera del PC objetivo

## V0.4.1 - Gmail

- [ ] OAuth 2.0 sin guardar contrasena de Gmail
- [ ] Leer correos recientes/no leidos
- [ ] Resumir y priorizar correos entrantes
- [ ] Preparar borradores de respuesta
- [ ] Preguntar antes de enviar
- [ ] `send_email` clasificado como CONFIRM
- [ ] Notificaciones/sincronizacion incremental

## V0.4.2 - LinkedIn y otros conectores

- [ ] Evaluar acceso oficial disponible para LinkedIn Messaging
- [ ] No depender de scraping ni automatizacion fragil del navegador para mensajeria
- [ ] Si existe acceso oficial adecuado: leer mensajes y preparar borradores
- [ ] Envio de mensajes siempre con confirmacion inicialmente
- [ ] Reutilizar el mismo modelo de conectores y Tool Router

## V0.5 - voz y moto

- [ ] Speech-to-Text
- [ ] Text-to-Speech
- [ ] Modo conduccion
- [ ] Intercom Bluetooth
- [ ] Activacion desde boton del intercom

## V1 - servidor 24/7 y hogar

- [ ] Evaluar mini PC x86 vs Raspberry Pi segun precios del momento
- [ ] Migrar Celeste Core sin reescritura
- [ ] Tailscale/WireGuard
- [ ] Home Assistant
- [ ] Echo Dot / Alexa
