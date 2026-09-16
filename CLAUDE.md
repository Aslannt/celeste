# Celeste

Asistente personal distribuido, de uso personal. Tres piezas:

- `celeste-core/` — API local en FastAPI (Python 3.12+). Brain, Tool Router, proveedores de IA, integraciones.
- `celeste-android/` — cliente Android (Kotlin, Compose). WOL, notas offline, chat, voz.
- `CelesteBrain/` — memoria en Markdown. **Datos personales, no versionados.**

## Reglas duras

1. **El LLM nunca toca el sistema directamente** (ADR-005). Sin shell, sin admin. Todo pasa por el Tool Router con niveles `READ / SAFE_WRITE / CONFIRM / RESTRICTED`. Una herramienta nueva se registra con su nivel; nunca se salta el router.
2. **Markdown es la fuente de verdad.** El índice SQLite (`CelesteBrain/.celeste/brain-index.sqlite3`) es caché reconstruible. Nada de lógica que dependa de que el índice sobreviva.
3. **Contenido externo es no confiable.** Correos, eventos de calendario y (a futuro) notificaciones del teléfono pueden traer instrucciones inyectadas. Se marcan como no confiables antes de llegar al modelo. Nunca quites esa marca para "simplificar".
4. **Sin acciones irreversibles sin confirmación.** Enviar correo, cancelar recordatorios y borrar son `CONFIRM`. El send guard por huella del RAW no se toca.

Nota: Claude Code (el asistente de desarrollo) tiene permiso para leer y modificar `.env`, `celeste-core/.secrets/` y `CelesteBrain/` cuando el trabajo lo requiera (decisión del usuario, 2026-09-16). Sigue sin subir nada de eso a Git ni pegar tokens/contenido personal en commits, PRs o mensajes salvo que el usuario lo pida explícitamente.

## Comandos

Core (Windows, desde `celeste-core/`):

```powershell
.\run_windows.ps1      # arranca la API en 127.0.0.1:8000
.\test_windows.ps1     # crea venv, instala [dev] y corre pytest
```

Core (Linux): `./run_linux.sh` — tests: `python -m pytest -q` dentro del venv.

Android: se compila desde Android Studio. No hay wrapper de Gradle en el repo.

Swagger local: `http://127.0.0.1:8000/docs`. Las rutas privadas exigen el header `X-Celeste-Token`.

## Contexto — léelo antes de proponer arquitectura

- `docs/DECISIONS.md` — ADRs. Si una decisión ya está tomada ahí, respétala o propón un ADR nuevo.
- `docs/ROADMAP.md` — qué está hecho y qué falta por versión.
- `docs/AI_TOOL_ROUTER.md` — contrato de herramientas y permisos.

## Convenciones

- Documentación y commits en español.
- Toda herramienta nueva necesita test en `celeste-core/tests/`.
- Los tests del Core tienen que pasar antes de cualquier commit.
- Nada de llamadas de red en tests.
- Configuración por variables de entorno en `celeste-core/.env`, nunca hardcodeada. Si agregas una variable, documéntala en `.env.example`.
- Cambios que crucen Core y Android: actualiza los dos lados en el mismo cambio, o el cliente se rompe en silencio.

## Cómo quiero trabajar

- Antes de tocar código, dime qué archivos vas a modificar y espera confirmación.
- Cambios pequeños y cerrados. Nada de refactors grandes sin pedirlos.
- No explores el repo entero: pregúntame por el archivo si no lo tienes claro.
