from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.tools import ToolRouter


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
        return self._router.tool_schemas()

    def execute(self, name: str, arguments: dict[str, Any]):
        return self._router.execute(name, arguments)

    def __getattr__(self, name: str):
        return getattr(self._router, name)


def scope_router_for_message(router: ToolRouter, message: str) -> ToolSchemaView:
    return ToolSchemaView(router, expose_tools=message_needs_tool_catalog(message))
