# Decisiones de arquitectura

## ADR-001: construir Celeste con arquitectura propia

Se estudiaran proyectos externos tipo JARVIS como referencia de implementaciones, pero no seran la base del codigo de Celeste. Celeste debe ser multiplataforma y distribuida desde el diseno.

## ADR-002: Markdown como fuente de verdad humana

Las notas y recuerdos importantes deben permanecer en formatos abiertos. La base de datos futura sera un indice/cache reconstruible, no la unica copia del conocimiento.

## ADR-003: no usar IA en V0.1

El Core debe funcionar sin LLM. Primero se valida red, almacenamiento y Android-PC.

## ADR-004: no resolver conflictos destructivamente

Cuando exista sincronizacion bidireccional, un conflicto de contenido humano no debe resolverse con Last-Write-Wins silencioso. Celeste preservara ambas versiones hasta poder fusionarlas.

## ADR-005: privilegios minimos

Un LLM nunca recibira shell/sudo/administrador irrestricto. Toda accion del sistema pasara por herramientas declaradas y politicas de permiso.

## ADR-006: modelo Ollama chico por defecto mientras el Core corre por CPU

`CELESTE_LLM_MODEL` local se bajo de `qwen3.5:9b` a `qwen3.5:4b` (2026-09-04). El PC actual no tiene GPU compatible para acelerar Ollama (Core corre 100% CPU), y para el caso de uso de voz (V0.5) la latencia importa mas que la calidad marginal de un modelo mas grande: una respuesta lenta rompe la sensacion de "asistente" cuando se habla en vivo. Este es un ajuste de config local en `.env` (no versionado), no un cambio de codigo. Revisar de nuevo cuando el PC tenga GPU NVIDIA (Ollama acelera bien con CUDA); ahi probablemente conviene volver a `qwen3.5:9b` o subir a un modelo mayor.

## ADR-007: LinkedIn Messaging queda en espera, sin acceso oficial gratuito

`docs/LINKEDIN_INTEGRATION_ASSESSMENT.md` (2026-08-18) ya habia concluido que la Messages API oficial de LinkedIn esta restringida a partners aprobados y que el self-serve abierto (`profile`, `email`, `w_member_social`) no cubre inbox/mensajes personales. Reverificado en 2026-09-15: sigue igual. Ademas, los intermediarios de terceros que si dan acceso (Unipile y similares) son servicios de pago, no la API oficial: violan la regla de "costo 0" de Celeste ademas de la ya documentada de no automatizacion fragil/no oficial.

Decision: no implementar el conector de LinkedIn Messaging mientras no exista una via oficial, gratuita y accesible para un individuo. El item queda en el roadmap como bloqueado, no descartado (ver disparador de reevaluacion en `LINKEDIN_INTEGRATION_ASSESSMENT.md`).

## ADR-008: CelesteBrain vive dentro del vault de Obsidian del usuario

Decidido 2026-09-16. El usuario ya usa activamente un vault de Obsidian personal (`Documents/Vault Personal`, con notas de casa, trabajo y una bitacora manual propia sobre este mismo proyecto en `Celeste/`). Para que las notas y recordatorios que Celeste genera sean visibles/enlazables desde la misma herramienta que ya usa a diario, `CELESTE_BRAIN_DIR` se movio a `Vault Personal/CelesteBrain/` (config local en `.env`, no en codigo).

Alcance deliberadamente acotado: solo se migro el contenido que la propia app genera (notas, recordatorios, indice, notificaciones). No se fusiono con el resto del vault (contratos, reuniones, vida personal) ni se le dio a `search_memory` acceso a esas notas existentes - eso cambiaria que datos puede mencionar la IA en voz alta y es una decision de alcance/privacidad mayor que amerita evaluarse aparte, no decidirse de forma apurada.

La copia original quedo renombrada como backup junto al repo (`CelesteBrain.pre-obsidian-backup-*`), no borrada, hasta confirmar que la migracion es estable.

## ADR-009: resumenes de datos reales nunca se generan libremente con el LLM

Descubierto 2026-09-16 implementando el resumen proactivo matutino (V0.5.1). La primera version pedia a `qwen3.5:9b` un "resumen breve de mi dia" en lenguaje libre, con `list_reminders`/`search_memory` disponibles como herramientas. El modelo no las llamo: broto una agenda entera inventada (una llamada a una persona que no existe, una clase de yoga, una cita al dentista) con el mismo tono seguro que si fuera real. Con las herramientas disponibles y el mensaje conteniendo cues claros ("recordatorios", "pendiente", "hoy"), el modelo igual opto por narrar en vez de consultar.

Esto es la misma clase de riesgo que las honesty-suffixes de `search_memory` ya mitigan para resultados de busqueda (ver `llm_tool_scope.py`), pero mas grave: aqui no hubo ninguna llamada a herramienta que el usuario pudiera auditar via "Detalles" en la UI, solo texto plausible.

Decision: cualquier resumen que el usuario vaya a confiar como "esto es lo que tengo de verdad" (recordatorios pendientes, agenda del dia, y a futuro inbox/calendario) se construye leyendo la API directamente en el cliente (o en un fast path deterministico en Core) y armando el texto en codigo, nunca dejando que el modelo redacte el contenido factual libremente. El LLM puede fungir para conversacion abierta (ver memoria de conversacion) pero no para narrar datos personales que deban ser exactos.

## ADR-010: memoria semantica - `bge-m3` + hibrido RRF sobre el mismo SQLite

Decidido 2026-09-16, primera gran apuesta de la sesion de planeacion previa ("segundo cerebro"): FTS5 solo resuelve coincidencia exacta de palabra y no el caso de uso real ("que era lo del tipo del banco"). Se agrega una capa de embeddings sobre `search_memory` sin tocar su interfaz externa.

- **Modelo**: `bge-m3` via Ollama, no `nomic-embed-text` - verificado que este ultimo es principalmente ingles, mientras `bge-m3` esta entrenado para +100 idiomas con un espacio semantico comun, y todas las notas de Celeste estan en espanol. Gratis, local, 1024 dimensiones, 1.2GB.
- **Almacenamiento**: nada de una base de datos vectorial aparte ni una extension nativa de SQLite (sqlite-vec) - eso es infraestructura para millones de documentos. El vector de cada nota se guarda como BLOB en el mismo `brain-index.sqlite3`; la similitud de coseno se calcula en Python puro al buscar (a escala personal, cientos de notas, esto es microsegundos). El indice sigue siendo 100% reconstruible (ADR-002).
- **Ranking**: Reciprocal Rank Fusion entre la lista de FTS5 y la semantica, combinando por posicion en vez de normalizar bm25 contra coseno (escalas no comparables).
- **Costo de arranque**: cada nota guarda un hash de su contenido; reconstruir el indice solo re-embebe notas nuevas o cambiadas, no todas cada vez. Los embeddings de un `rebuild()` se piden en un solo batch, no uno por nota.
- **Resiliencia**: deshabilitado por defecto (`CELESTE_EMBEDDINGS_ENABLED=false`), mismo patron opt-in que Gmail/Calendar - requiere `ollama pull bge-m3` primero. Si Ollama o el modelo fallan, la busqueda degrada sola a FTS5 y la escritura de notas nunca se bloquea (timeout corto de 5s en el cliente de embeddings, para no colgar `create_note` si Ollama esta caido).

Encontrado en el camino: los tests de Celeste cargan `celeste-core/.env` real via `Settings.from_env()` (`override=False`), asi que cualquier variable nueva no mockeada explicitamente por un test hereda lo que sea que tenga el `.env` del desarrollador. Se agrego `tests/conftest.py` con un fixture autouse que fija `CELESTE_EMBEDDINGS_ENABLED=false` por defecto en toda la suite, para que activar la funcionalidad en el `.env` real no vuelva a contaminar tests que no la mencionan.
