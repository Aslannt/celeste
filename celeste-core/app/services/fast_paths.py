from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.services.tools import ToolExecution, ToolRouter


_CREATE_PATTERNS = [
    re.compile(r"^\s*(?:recuerda|guarda|anota)\s+que\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"^\s*(?:acu[eé]rdate)\s+(?:de\s+)?que\s+(.+?)\s*$", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"^\s*crea\s+(?:una\s+)?nota(?:\s+que\s+diga|\s+sobre)?\s+(.+?)\s*$",
        re.IGNORECASE | re.DOTALL,
    ),
]

_PC_STATUS_PATTERNS = [
    re.compile(
        r"^(?:(?:cual es|dime|muestra|consulta|revisa|como esta|que tal esta) )?"
        r"(?:el )?estado (?:del )?(?:pc|computador|ordenador|core)$"
    ),
    re.compile(r"^estado (?:del )?(?:pc|computador|ordenador|core)$"),
]

_SEARCH_PATTERNS = [
    re.compile(r"^(?:busca|buscar) (?:en (?:mi )?memoria )?(.+)$"),
    re.compile(
        r"^(?:que recuerdas|que sabes) (?:de|sobre) (.+?)"
        r"(?: busca (?:en )?(?:mi )?memoria)?$"
    ),
    re.compile(r"^no te habia dicho que (.+?) revisa si recuerdas algo$"),
]

_MUTATION_WORDS = (
    " elimina",
    " eliminar",
    " borra",
    " borrar",
    " modifica",
    " modificar",
    " actualiza",
    " actualizar",
    " cambia",
    " cambiar",
    " edita",
    " editar",
)


@dataclass(frozen=True)
class FastPathResult:
    reply: str
    events: list[ToolExecution]
    performance: dict[str, Any]
    provider: str = "core_fast_path"

    def to_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "provider": self.provider,
            "events": [event.to_dict() for event in self.events],
            "performance": self.performance,
        }


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold().strip()


def _intent_text(value: str) -> str:
    text = _plain(value)
    text = re.sub(r"[¿?¡!.,;:]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _create_arguments(message: str) -> dict[str, Any] | None:
    text = message.strip()
    for pattern in _CREATE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        content = match.group(1).strip()
        if not content:
            return None
        first_line = content.splitlines()[0].strip()
        title = first_line.split(".", 1)[0].strip()[:100] or "Nota de Celeste"
        return {
            "title": title,
            "content": content,
            "type": "note",
            "tags": ["assistant"],
        }
    return None


def _pc_status_requested(message: str) -> bool:
    text = _intent_text(message)
    return any(pattern.fullmatch(text) for pattern in _PC_STATUS_PATTERNS)


def _search_query(message: str) -> str | None:
    text = _intent_text(message)
    padded = f" {text} "
    if any(word in padded for word in _MUTATION_WORDS):
        return None

    for pattern in _SEARCH_PATTERNS:
        match = pattern.fullmatch(text)
        if not match:
            continue
        query = match.group(1).strip()
        query = re.sub(r"^(?:mi|mis|el|la|los|las)\s+", "", query).strip()
        return query or None
    return None


def _search_reply(query: str, event: ToolExecution) -> str:
    notes = event.output if event.status == "executed" and isinstance(event.output, list) else []
    if not notes:
        return f"No encontre nada en Celeste Brain sobre '{query}'."

    lines: list[str] = []
    for note in notes[:5]:
        if not isinstance(note, dict):
            continue
        title = str(note.get("title") or "Nota").strip()
        content = str(note.get("content") or "").strip().replace("\n", " ")
        if content and content.casefold() != title.casefold():
            lines.append(f"- {title}: {content[:220]}")
        else:
            lines.append(f"- {title}")
    if not lines:
        return f"No encontre nada en Celeste Brain sobre '{query}'."
    return "Encontre esto en Celeste Brain:\n" + "\n".join(lines)


def _result(
    *,
    settings: Settings,
    started: float,
    fast_path: str,
    event: ToolExecution,
    tool_started: float,
    reply: str,
) -> FastPathResult:
    return FastPathResult(
        reply=reply,
        events=[event],
        performance={
            "model": settings.llm_model,
            "model_used": False,
            "fast_path": fast_path,
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
            "ollama_rounds": [],
            "tools": [
                {
                    "tool": event.tool,
                    "duration_ms": round((time.perf_counter() - tool_started) * 1000, 2),
                    "source": "core_fast_path",
                }
            ],
        },
    )


def try_ollama_fast_path(
    message: str,
    router: ToolRouter,
    settings: Settings,
) -> FastPathResult | None:
    """Handle unambiguous local intents without paying for an LLM round.

    Fast paths only cover READ and SAFE_WRITE operations. CONFIRM operations remain
    in the normal provider + Tool Router flow so this optimization cannot bypass a
    user confirmation boundary.
    """

    if settings.llm_provider != "ollama":
        return None

    started = time.perf_counter()

    create_arguments = _create_arguments(message)
    if create_arguments is not None:
        tool_started = time.perf_counter()
        event = router.execute("create_note", create_arguments)
        if event.status == "executed":
            output = event.output if isinstance(event.output, dict) else {}
            title = str(output.get("title") or create_arguments["title"])
            reply = f"Listo. Guarde '{title}' en Celeste Brain."
        else:
            reply = event.summary or "No pude guardar la nota en Celeste Brain."
        return _result(
            settings=settings,
            started=started,
            fast_path="create_note",
            event=event,
            tool_started=tool_started,
            reply=reply,
        )

    if _pc_status_requested(message):
        tool_started = time.perf_counter()
        event = router.execute("get_pc_status", {})
        output = event.output if isinstance(event.output, dict) else {}
        reply = (
            f"Celeste Core esta {output.get('status', 'desconocido')} en "
            f"{output.get('hostname', 'este equipo')} ({output.get('os', 'SO desconocido')})."
        )
        return _result(
            settings=settings,
            started=started,
            fast_path="get_pc_status",
            event=event,
            tool_started=tool_started,
            reply=reply,
        )

    query = _search_query(message)
    if query is not None:
        tool_started = time.perf_counter()
        event = router.execute("search_memory", {"query": query, "limit": 5})
        return _result(
            settings=settings,
            started=started,
            fast_path="search_memory",
            event=event,
            tool_started=tool_started,
            reply=_search_reply(query, event),
        )

    return None
