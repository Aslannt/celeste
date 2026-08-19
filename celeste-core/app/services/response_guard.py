from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.tools import ToolExecution


_PRIORITY_PATTERNS = (
    re.compile(r"\b(?:que|qué)\b.{0,80}\bprimero\b"),
    re.compile(r"\bpriori(?:za|zar|dad|dades)\b"),
    re.compile(r"\borden(?:a|ar)?\b.{0,80}\b(?:tarea|nota|pendiente)s?\b"),
    re.compile(r"\b(?:que|qué) (?:me )?recomiendas\b"),
)

_SCHEDULE_CLAIM_PATTERNS = (
    re.compile(r"\b(?:recordatorio|tarea|evento)\b.{0,48}\bprogramad[oa]s?\b"),
    re.compile(r"\b(?:ya tienes|hay)\b.{0,72}\bprogramad[oa]s?\b"),
    re.compile(r"\bte (?:recordare|avisare|notificare)\b"),
)


def _plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _asks_for_priority(message: str) -> bool:
    text = _plain(message)
    return any(pattern.search(text) for pattern in _PRIORITY_PATTERNS)


def _claims_schedule(reply: str) -> bool:
    text = _plain(reply)
    return any(pattern.search(text) for pattern in _SCHEDULE_CLAIM_PATTERNS)


def _memory_results(events: list[ToolExecution]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for event in events:
        if event.tool != "search_memory" or event.status != "executed":
            continue
        if not isinstance(event.output, list):
            continue
        matches = [item for item in event.output if isinstance(item, dict)]
    return matches


def _grounded_memory_reply(notes: list[dict[str, Any]], *, priority_requested: bool) -> str:
    lines: list[str] = []
    for note in notes[:5]:
        title = str(note.get("title") or "Nota").strip()
        content = str(note.get("content") or "").strip().replace("\n", " ")
        if content and content.casefold() != title.casefold():
            lines.append(f"- {title}: {content[:220]}")
        else:
            lines.append(f"- {title}")

    reply = "Encontre estas notas en Celeste Brain:\n" + "\n".join(lines)
    if priority_requested:
        reply += (
            "\n\nCon lo que esta guardado no puedo determinar con certeza cual deberias "
            "hacer primero: las notas no establecen una prioridad ni una urgencia comparable. "
            "Puedo ordenarlas si me das un criterio, por ejemplo seguridad, costo o tiempo."
        )

    if any(
        str(note.get("type") or "").casefold() == "task"
        or "recordatorio" in {str(tag).casefold() for tag in note.get("tags") or []}
        or "recordatorio" in _plain(str(note.get("title") or ""))
        for note in notes
    ):
        reply += (
            "\n\nNota: que una entrada sea de tipo task o use texto de recordatorio solo "
            "describe lo guardado en Brain; no demuestra que exista una notificacion activa."
        )
    return reply


def guard_memory_reply(
    message: str,
    reply: str,
    events: list[ToolExecution],
) -> tuple[str, bool]:
    """Replace unsafe memory-based conclusions with a deterministic grounded reply.

    The guard is deliberately narrow: it only considers pure search_memory turns.
    Mutating or confirmation flows are left untouched. Priority requests are always
    grounded because the model cannot safely invent an urgency order from notes.
    Other memory replies are replaced only when they claim scheduling that no
    scheduler tool established.
    """

    if not events or any(event.tool != "search_memory" for event in events):
        return reply, False

    notes = _memory_results(events)
    if not notes:
        return reply, False

    priority_requested = _asks_for_priority(message)
    schedule_claimed = _claims_schedule(reply)
    if not priority_requested and not schedule_claimed:
        return reply, False

    return _grounded_memory_reply(notes, priority_requested=priority_requested), True


def sanitize_public_events(events: Any) -> Any:
    """Remove provider-only metadata before assistant events leave Celeste Core."""

    if not isinstance(events, list):
        return events

    sanitized: list[Any] = []
    for event in events:
        if not isinstance(event, dict):
            sanitized.append(event)
            continue

        public_event = dict(event)
        output = public_event.get("output")
        if isinstance(output, list):
            public_output: list[Any] = []
            for item in output:
                if isinstance(item, dict):
                    public_item = {
                        key: value
                        for key, value in item.items()
                        if not str(key).startswith("_celeste_")
                    }
                    public_output.append(public_item)
                else:
                    public_output.append(item)
            public_event["output"] = public_output
        sanitized.append(public_event)
    return sanitized
