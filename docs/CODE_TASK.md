# code_task: delegar codigo a un agente en sandbox

Celeste no escribe codigo por si misma. `code_task` prepara un brief y un script listo para correr; el agente de codigo (Claude Code CLI) corre dentro de un contenedor Docker aislado, y **el usuario ejecuta ese script el mismo**, revisandolo antes. Ver [ADR-011](DECISIONS.md).

## Por que Celeste no lo ejecuta ella misma

ADR-005 dice que el LLM nunca toca el sistema directamente. `code_task` aplica el mismo principio un nivel arriba: tampoco la propia automatizacion de Celeste debe ser la que dispare un agente de codigo autonomo sin que un humano apriete el boton. Por eso:

- `code_task` **no esta registrado en el Tool Router**. La conversacion normal con Celeste (`/api/v1/assistant/chat`) no puede llegar a el, ni para preparar un brief.
- `POST /api/v1/code-task/prepare/{brief_id}` genera un script `.ps1` en `celeste-core/.secrets/code-task-runs/`, pero no lo corre. El usuario lo revisa y lo ejecuta el mismo.
- El script, al terminar, le avisa a Celeste el resultado (`POST /api/v1/code-task/record`) para guardarlo en Brain - eso si es automatico, porque guardar un resultado no es lo mismo que generarlo.

## Setup (una sola vez)

1. Tener Docker instalado y corriendo.
2. Construir la imagen:

   ```powershell
   cd celeste-core/docker/code-task
   docker build -t celeste-code-task .
   ```

3. Generar un token de uso no interactivo con tu sesion de Claude ya paga (no es una API key que cobre aparte):

   ```powershell
   claude setup-token
   ```

4. Copiar el resultado a `celeste-core/.env`:

   ```dotenv
   CELESTE_CODE_TASK_OAUTH_TOKEN=<lo que devolvio claude setup-token>
   ```

## Flujo

```text
POST /api/v1/code-task/brief         -> arma y guarda el brief (10 min de vida)
POST /api/v1/code-task/prepare/{id}  -> genera el script .ps1, consume el brief
(el usuario revisa y corre el script el mismo)
POST /api/v1/code-task/record        -> el script llama esto solo al terminar
```

El brief sigue la plantilla fija de la seccion 3.5 del documento de diseno: objetivo, archivos relevantes, criterio de aceptacion, restricciones, si debe correr tests. Por ahora es un formulario (los campos los llena el usuario directamente); la version con el modelo local completando huecos y preguntando solo lo que falte (maximo 3 preguntas) queda para una iteracion futura, una vez validado el ciclo de ejecucion.

## Aislamiento

- El contenedor solo monta el repositorio objetivo (`-v <repo>:/workspace`); no ve el resto del PC, ni `.env`, ni `CelesteBrain`.
- Lista blanca de repositorios permitidos: `CELESTE_CODE_TASK_ALLOWED_DIRS` (por defecto, solo este repo).
- Limites de memoria (4g) y CPU (2), y un timeout duro (`CELESTE_CODE_TASK_TIMEOUT_SECONDS`, default 600s) en el propio script.
- **Sin bypass de permisos.** El contenedor tiene red normal (necesaria para instalar dependencias), y la propia documentacion de Claude Code recomienda `--allow-dangerously-skip-permissions` solo para sandboxes *sin* red - con red, un bypass total podria dejar que el agente saque su propio token por internet. En vez de eso se usa `--allowedTools` acotado a edicion de archivos (`Edit`, `Write`, `Read`, `Glob`, `Grep`) y comandos especificos de este proyecto (`python -m pytest`, `pip install`, `git status`, `git diff`) - nada de red arbitraria desde dentro de la sesion del agente.
- El script generado contiene el token en texto plano; vive en `celeste-core/.secrets/` (ya ignorado por Git). Borralo cuando ya no lo necesites.

## Fuera de alcance de esta primera version

- Enrutar entre proveedores si se agota la cuota (bounce-router, fallback a Ollama local) - seccion 3.4 del documento original, pendiente.
- Acceso desde el celular/moto - depende de la infraestructura de dos nodos (seccion 3.6), que no existe todavia.
