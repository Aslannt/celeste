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
- [ ] Validar sincronizacion idempotente Android -> Core

## V0.2 - IA y Tool Router

- [ ] Abstraccion de proveedores LLM
- [ ] Tool Router con niveles READ / SAFE_WRITE / CONFIRM / RESTRICTED
- [ ] `create_note`
- [ ] `search_memory`
- [ ] `get_pc_status`
- [ ] `wake_pc`
- [ ] Confirmaciones de acciones sensibles

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
