# Idempotencia de notas Android -> Core

Celeste Android guarda cada nota nueva primero en Room con un `localId` UUID. Ese identificador se envia a Celeste Core en el header `X-Celeste-Idempotency-Key`.

Celeste Core persiste la clave en el frontmatter Markdown como `idempotency_key`.

- Si recibe de nuevo la misma clave y el mismo contenido, devuelve la nota existente en lugar de crear otro archivo.
- Si la misma clave llega con contenido distinto, responde HTTP 409 para no ocultar una colision o reutilizacion accidental.
- Las notas creadas por otros clientes pueden omitir el header y siguen funcionando como antes.

Esto cierra la ventana de duplicados que existia en V0.2 cuando Core podia crear el Markdown pero Android perder la respuesta antes de eliminar la fila `PENDING`.
