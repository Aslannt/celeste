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
- [x] `update_note` y `delete_note` protegidos por CONFIRM
- [x] Infraestructura de confirmacion, cancelacion y expiracion
- [x] Auditoria local de herramientas sin guardar argumentos/contenido privado
- [x] Endpoint `POST /api/v1/assistant/chat`
- [x] Interfaz Android para hablar con Celeste
- [x] Interfaz Android Confirmar/Cancelar para acciones sensibles
- [x] OpenAI con `store=false` y herramientas serializadas
- [x] Validar proveedor local y herramientas basicas en el PC real
- [ ] Revalidar tests Core tras el hardening de confirmaciones/auditoria
- [ ] Compilar/validar la UI final de confirmaciones en Android real
- [ ] Configurar y validar un proveedor LLM real
- [ ] `wake_pc` como herramienta cuando Core pueda ejecutarse fuera del PC objetivo

## V0.4.1 - Gmail

- [x] Cliente Gmail API oficial con OAuth 2.0 local
- [x] Mantener credenciales/token OAuth fuera de Git
- [x] Helper local de autorizacion OAuth para Windows
- [x] `gmail_list_unread` como READ
- [x] `gmail_search` como READ
- [x] `gmail_read_message` como READ y contenido marcado como no confiable
- [x] `gmail_create_draft` como SAFE_WRITE
- [x] `gmail_create_reply_draft` como SAFE_WRITE
- [x] `gmail_send_draft` como CONFIRM
- [x] Flujo borrador -> confirmacion -> envio
- [x] Proteccion contra instrucciones maliciosas contenidas en correos
- [ ] Ejecutar tests automatizados del incremento Gmail
- [ ] Autorizar la cuenta Gmail real en el PC
- [ ] Validar lectura de correos reales
- [ ] Validar creacion de un borrador real sin envio
- [ ] Validar Cancelar y luego Confirmar con un correo de prueba inocuo
- [ ] Resumir/priorizar correos con proveedor LLM real
- [ ] Notificaciones/sincronizacion incremental para uso 24/7

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
