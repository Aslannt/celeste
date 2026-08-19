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

- [x] Abstraccion de proveedores (`local_rules` / `ollama` / `openai`)
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
- [x] Ollama local con `qwen3.5:9b`
- [x] Revalidar tests Core tras hardening de confirmaciones/auditoria
- [x] Compilar y validar UI de confirmaciones en Android real
- [x] Optimizar latencia con fast paths, tool scoping, keep-alive y grounding
- [ ] `wake_pc` como herramienta cuando Core pueda ejecutarse fuera del PC objetivo

## V0.4.1 - Gmail

- [x] Cliente Gmail API oficial con OAuth 2.0 local
- [x] Mantener credenciales/token OAuth fuera de Git
- [x] Helper local de autorizacion OAuth para Windows
- [x] `gmail_list_unread` como READ
- [x] Fast path para no leidos sin Ollama
- [x] `gmail_search` como READ
- [x] `gmail_read_message` como READ y contenido marcado como no confiable
- [x] `gmail_create_draft` como SAFE_WRITE
- [x] `gmail_create_reply_draft` como SAFE_WRITE
- [x] `gmail_send_draft` como CONFIRM
- [x] Flujo borrador -> confirmacion -> envio
- [x] Send guard por huella del RAW exacto confirmado
- [x] Proteccion contra instrucciones maliciosas contenidas en correos
- [x] Tests automatizados del incremento Gmail
- [x] Autorizar la cuenta Gmail real en el PC
- [x] Validar lectura de correos reales
- [x] Validar creacion de un borrador real sin envio
- [x] Validar Cancelar y luego Confirmar con correo inocuo
- [x] Validar que editar tras pedir confirmacion invalida el envio
- [x] Validar flujo natural Ollama -> Tool Router -> CONFIRM -> envio
- [x] Monitor manual de no leidos -> notificaciones locales
- [x] Deduplicacion del monitor
- [x] Crear borrador de respuesta real en el hilo correcto
- [ ] Resolver configuracion OAuth persistente para uso diario
- [ ] Activar monitor periodico solo despues de la decision OAuth
- [ ] Integrar mejor resumen/priorizacion de inbox en la experiencia diaria

## V0.4.2 - Calendar y recordatorios reales

- [x] Disenar recordatorios locales durables separados de notas Brain
- [x] Crear almacenamiento local de recordatorios
- [x] Crear monitor que convierte recordatorios vencidos en notificaciones Celeste
- [x] `list_reminders` como READ
- [x] `create_reminder` como SAFE_WRITE
- [x] `complete_reminder` como SAFE_WRITE
- [x] `cancel_reminder` como CONFIRM
- [x] Exponer API de recordatorios a Android
- [x] Cliente oficial Google Calendar API v3
- [x] OAuth Desktop local separado para Calendar
- [x] `calendar_list_events` y `calendar_get_event` como READ
- [x] `calendar_create_event` como SAFE_WRITE sin asistentes
- [x] `calendar_update_event` y `calendar_delete_event` como CONFIRM
- [x] Marcar contenido Calendar como externo/no confiable
- [x] Inyectar reloj local actual en schemas de scheduling para resolver expresiones relativas
- [x] Modelos/metodos Android para Calendar y recordatorios
- [ ] CI final en verde
- [ ] Autorizar Calendar en el PC real
- [ ] Validar lectura y CRUD de eventos inocuos
- [ ] Validar un recordatorio real y su notificacion
- [ ] Validar intents naturales como `recuerdame manana a las 8`
- [ ] Integrar agenda/recordatorios en la UI final Android
- [ ] Evaluar recurrencia de recordatorios tras validar one-shot

## V0.4.3 - Android UX y conectores secundarios

- [x] Crear sistema visual propio Celeste light/dark
- [x] Redisenar home, asistente, inbox, Brain y estado offline
- [ ] Validar visualmente el APK en telefono real
- [ ] Integrar calendario y recordatorios sobre el nuevo lenguaje visual
- [ ] Evaluar acceso oficial disponible para LinkedIn Messaging
- [ ] No depender de scraping ni automatizacion fragil del navegador para mensajeria
- [ ] Si existe acceso oficial adecuado: leer mensajes y preparar borradores
- [ ] Envio de mensajes siempre con confirmacion inicialmente

## V0.5 - voz y moto

- [ ] Speech-to-Text
- [ ] Text-to-Speech
- [ ] Modo conduccion
- [ ] Intercom Bluetooth
- [ ] Activacion desde boton del intercom

## V0.6 - asistente personal diario

- [ ] Vista diaria combinando agenda, recordatorios, inbox y Brain
- [ ] Rutinas de manana/noche configurables
- [ ] Notificaciones Android fiables en background
- [ ] Persistencia de confirmaciones importantes ante reinicios donde sea seguro
- [ ] Backup/restauracion de Brain y datos locales
- [ ] Pruebas de ejecucion prolongada y recuperacion ante fallos

## V1 - servidor 24/7 y hogar

- [ ] Evaluar mini PC x86 vs Raspberry Pi segun precios del momento
- [ ] Migrar Celeste Core sin reescritura
- [ ] Tailscale/WireGuard
- [ ] `wake_pc` desde el Core 24/7
- [ ] Home Assistant
- [ ] Echo Dot / Alexa
- [ ] Validacion final de seguridad, backups y operacion diaria
