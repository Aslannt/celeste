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

V0.3 es busqueda lexical local. No usa embeddings, RAG ni un proveedor LLM.
