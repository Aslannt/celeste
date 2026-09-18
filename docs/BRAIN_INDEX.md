# Celeste Brain Index

Celeste Brain conserva Markdown como fuente de verdad. SQLite no reemplaza las notas ni se considera almacenamiento primario.

## V0.3

El indice vive en:

```text
CelesteBrain/.celeste/brain-index.sqlite3
```

Se usa SQLite FTS5 para indexar:

- titulo;
- contenido;
- tags.

Los campos `note_id`, `note_type` y `updated_at` se guardan en la tabla virtual para recuperar y ordenar resultados, pero la respuesta final siempre se vuelve a leer desde el Markdown original.

Como el indice es cache reconstruible (regla dura 2 de `CLAUDE.md`), `.celeste/*.sqlite3*` debe quedar excluido de la sincronizacion del vault (Syncthing u otra herramienta similar) igual que se excluiria cualquier binario derivado: sincronizar un `.sqlite3` a medio escribir entre dos maquinas puede corromper el archivo, y de todas formas se reconstruye solo al arrancar Core.

## Ciclo de vida

- Al arrancar Celeste Core, el indice se reconstruye desde `CelesteBrain/notes`.
- Crear o actualizar una nota actualiza el indice.
- Eliminar una nota de forma logica la saca del indice de busqueda.
- `POST /api/v1/notes/index/rebuild` fuerza una reconstruccion manual, util si una persona edita Markdown directamente mientras Core esta encendido.
- El archivo SQLite puede borrarse: al siguiente arranque Core lo vuelve a crear desde Markdown.

## API de busqueda

```text
GET /api/v1/notes/search?q=<texto>&limit=20
```

La busqueda requiere el mismo `X-Celeste-Token` que el resto de endpoints de notas.

## Memoria semantica (hibrida FTS5 + embeddings)

Ademas de la coincidencia lexical, el mismo `brain-index.sqlite3` guarda un embedding por nota en la tabla `notes_embeddings` (vector como BLOB, sin extension nativa de SQLite ni base de datos vectorial aparte - a esta escala, similitud de coseno en Python puro sobre unos cientos de notas es microsegundos). Sigue siendo caché 100% reconstruible: se puede borrar el archivo y Core lo regenera, embeddings incluidos.

- Modelo: `bge-m3` via Ollama (`CELESTE_EMBEDDING_MODEL`, gratis, local, multilingue - elegido sobre `nomic-embed-text` porque las notas estan en espanol). Requiere `ollama pull bge-m3` una vez.
- Deshabilitado por defecto (`CELESTE_EMBEDDINGS_ENABLED=false`), mismo patron que Gmail/Calendar: hay que habilitarlo explicitamente despues de bajar el modelo.
- Cada nota guarda un hash de su contenido junto al vector; al reconstruir el indice solo se recalculan embeddings de notas nuevas o cambiadas, no todas cada vez.
- `search_ids` combina el ranking de FTS5 y el de similitud semantica por **Reciprocal Rank Fusion** (posicion, no score normalizado - bm25 y coseno viven en escalas distintas).
- Si Ollama o el modelo no responden, la busqueda degrada sola a solo-FTS5; nunca rompe `search_memory` ni la escritura de notas (ver [ADR-010](DECISIONS.md)).
- La interfaz de `search_memory` no cambio: mismo nombre, mismos parametros. El upgrade es interno a `BrainIndex`.
