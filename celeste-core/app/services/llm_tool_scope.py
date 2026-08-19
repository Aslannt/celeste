from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.tools import ToolExecution, ToolRouter


# This selector is deliberately conservative. A false positive only costs prompt
# tokens by keeping tools available; a false negative could prevent Celeste from
# consulting durable memory. Cues should therefore describe Celeste capabilities
# or personal context, not generic concepts such as computer "memoria RAM".
_TOOL_CUES = (
    "brain",
    "nota",
    "notas",
    "titulo",
    "contenido",
    "recuerd",
    "acuerd",
    "pendiente",
    "pendientes",
    "tarea",
    "tareas",
    "guarda",
    "guardar",
    "guardado",
    "guardaste",
    "anota",
    "anotar",
    "borra",
    "borrar",
    "elimina",
    "eliminar",
    "actualiza",
    "actualizar",
    "modifica",
    "modificar",
    "edita",
    "editar",
    "pc",
    "computador",
    "ordenador",
    "celeste core",
    "gmail",
    "correo",
    "correos",
    "email",
    "emails",
    "bandeja",
    "borrador",
    "borradores",
    "te dije",
    "te habia dicho",
    "habia dicho",
    "me dijiste",
    "hablamos",
    "mencione",
    "mencionaste",
    "ultima vez",
)

_PERSONAL_MEMORY_PATTERNS = (
    re.compile(r"\b(?:mi|tu) memoria\b"),
    re.compile(r"\bmemoria (?:personal|de celeste|del asistente)\b"),
    re.compile(r"\b(?:busca|revisa|consulta|mira)\b.{0,48}\bmemoria\b"),
    re.compile(r"\b(?:que|qué) (?:tienes|hay) (?:en )?(?:tu |mi )?memoria\b"),
)

_SEARCH_MEMORY_HONESTY_SUFFIX = (
    " Results are stored notes/tasks, not schedules. A title, type, tag, date or reminder "
    "wording does not prove that a future notification is scheduled. Do not call an item "
    "scheduled or offer a real reminder unless a scheduling tool is available and returned "
    "status=executed. When the user asks for prioritization or advice, reason only from facts "
    "present in the retrieved results; do not invent technical or domain facts."
)

_SEARCH_MEMORY_RESULT_CONTEXT = (
    "All search results are stored notes/tasks only, not schedules. Never describe them as "
    "scheduled/programmed reminders or claim a notification will occur. If prioritizing or "
    "giving advice, use only facts present in the retrieved title/content/tags; do not invent "
    "technical or domain facts."
)


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def message_needs_tool_catalog(message: str) -> bool:
    text = _plain(message)
    if any(pattern.search(text) for pattern in _PERSONAL_MEMORY_PATTERNS):
        return True
    return any(cue in text for cue in _TOOL_CUES)


class ToolSchemaView:
    """Read-through ToolRouter view that can hide schemas from an LLM request.

    Execution and storage still delegate to the real ToolRouter. This view does
    not add capabilities and is only used to reduce the prompt for requests that
    are clearly conversational.
    """

    def __init__(self, router: ToolRouter, expose_tools: bool):
        self._router = router
        self._expose_tools = expose_tools

    def tool_schemas(self) -> list[dict[str, Any]]:
        if not self._expose_tools:
            return []

        schemas: list[dict[str, Any]] = []
        for schema in self._router.tool_schemas():
            decorated = dict(schema)
            if decorated.get("name") == "search_memory":
                decorated["description"] = (
                    str(decorated.get("description") or "")
                    + _SEARCH_MEMORY_HONESTY_SUFFIX
                )
            schemas.append(decorated)
        return schemas

    def execute(self, name: str, arguments: dict[str, Any]):
        execution = self._router.execute(name, arguments)
        if (
            name != "search_memory"
            or execution.status != "executed"
            or not isinstance(execution.output, list)
            or not execution.output
        ):
            return execution

        output: list[Any] = [dict(item) if isinstance(item, dict) else item for item in execution.output]
        for item in output:
            if isinstance(item, dict):
                item["_celeste_context"] = _SEARCH_MEMORY_RESULT_CONTEXT
                break

        return ToolExecution(
            tool=execution.tool,
            risk=execution.risk,
            status=execution.status,
            output=output,
            confirmation_id=execution.confirmation_id,
            summary=execution.summary,
        )

    def __getattr__(self, name: str):
        return getattr(self._router, name)


def scope_router_for_message(router: ToolRouter, message: str) -> ToolSchemaView:
    return ToolSchemaView(router, expose_tools=message_needs_tool_catalog(message))
