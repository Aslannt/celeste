from __future__ import annotations

import platform
import socket
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable
from uuid import uuid4

from pydantic import ValidationError

from app.config import Settings
from app.models import NoteCreate, NoteUpdate
from app.services.audit import ToolAuditLog
from app.services.index import BrainIndex, BrainIndexError
from app.services.storage import MarkdownNoteStorage, NoteNotFoundError


class ToolRisk(StrEnum):
    READ = "READ"
    SAFE_WRITE = "SAFE_WRITE"
    CONFIRM = "CONFIRM"
    RESTRICTED = "RESTRICTED"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: ToolRisk
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    confirmation_summary: Callable[[dict[str, Any]], str] | None = None

    def function_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": False,
        }


@dataclass(frozen=True)
class PendingAction:
    confirmation_id: str
    tool: str
    arguments: dict[str, Any]
    summary: str
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmation_id": self.confirmation_id,
            "tool": self.tool,
            "summary": self.summary,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ToolExecution:
    tool: str
    risk: ToolRisk
    status: str
    output: Any = None
    confirmation_id: str | None = None
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tool": self.tool,
            "risk": self.risk.value,
            "status": self.status,
        }
        if self.output is not None:
            result["output"] = self.output
        if self.confirmation_id is not None:
            result["confirmation_id"] = self.confirmation_id
        if self.summary is not None:
            result["summary"] = self.summary
        return result


class ConfirmationStore:
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._items: dict[str, PendingAction] = {}

    def put(self, tool: str, arguments: dict[str, Any], summary: str) -> PendingAction:
        with self._lock:
            self._purge_expired()
            action = PendingAction(
                confirmation_id=str(uuid4()),
                tool=tool,
                arguments=dict(arguments),
                summary=summary,
                created_at=time.time(),
            )
            self._items[action.confirmation_id] = action
            return action

    def pop(self, confirmation_id: str) -> PendingAction | None:
        with self._lock:
            self._purge_expired()
            return self._items.pop(confirmation_id, None)

    def list(self) -> list[PendingAction]:
        with self._lock:
            self._purge_expired()
            return sorted(self._items.values(), key=lambda action: action.created_at)

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            key
            for key, action in self._items.items()
            if now - action.created_at > self.ttl_seconds
        ]
        for key in expired:
            self._items.pop(key, None)


_CONFIRMATIONS = ConfirmationStore()


class ToolRouter:
    """Security boundary between AI providers and Celeste capabilities.

    Providers only receive schemas from this router and all calls come back
    through execute(). No provider receives shell or filesystem access.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = MarkdownNoteStorage(settings.brain_dir)
        self.index = BrainIndex(settings.brain_dir)
        self.audit = ToolAuditLog(settings.brain_dir)
        self._tools: dict[str, ToolSpec] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        self.register(
            ToolSpec(
                name="search_memory",
                description=(
                    "Search Celeste Brain notes by words appearing in title, content or tags. "
                    "Use this instead of inventing remembered facts."
                ),
                risk=ToolRisk.READ,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text to search for."},
                        "limit": {
                            "type": "integer",
                            "description": "Maximum notes to return, from 1 to 10.",
                            "minimum": 1,
                            "maximum": 10,
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                handler=self._search_memory,
            )
        )
        self.register(
            ToolSpec(
                name="create_note",
                description=(
                    "Create a durable Markdown note in Celeste Brain. This is a SAFE_WRITE: when "
                    "the user clearly asks Celeste to remember, save or note something, call this "
                    "tool directly without asking for confirmation. Infer a concise title from the "
                    "user's content; type and tags are optional metadata that Celeste may infer."
                ),
                risk=ToolRisk.SAFE_WRITE,
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Concise title inferred from the user's content.",
                        },
                        "content": {
                            "type": "string",
                            "description": "The durable information the user asked Celeste to save.",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["note", "task", "memory", "project"],
                            "description": "Optional classification. Use note unless another type is clearly better.",
                            "default": "note",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional short tags inferred from the content; may be empty.",
                            "default": [],
                        },
                    },
                    "required": ["title", "content"],
                    "additionalProperties": False,
                },
                handler=self._create_note,
            )
        )
        self.register(
            ToolSpec(
                name="update_note",
                description=(
                    "Modify an existing Celeste Brain note. This changes human-owned memory and "
                    "therefore always requires explicit user confirmation."
                ),
                risk=ToolRisk.CONFIRM,
                parameters={
                    "type": "object",
                    "properties": {
                        "note_id": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": ["note", "task", "memory", "project"],
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["note_id"],
                    "additionalProperties": False,
                },
                handler=self._update_note,
                confirmation_summary=self._summarize_update_note,
            )
        )
        self.register(
            ToolSpec(
                name="delete_note",
                description=(
                    "Soft-delete an existing Celeste Brain note. The Markdown file is preserved "
                    "with deleted=true, and explicit user confirmation is required."
                ),
                risk=ToolRisk.CONFIRM,
                parameters={
                    "type": "object",
                    "properties": {"note_id": {"type": "string"}},
                    "required": ["note_id"],
                    "additionalProperties": False,
                },
                handler=self._delete_note,
                confirmation_summary=self._summarize_delete_note,
            )
        )
        self.register(
            ToolSpec(
                name="get_pc_status",
                description="Return the current Celeste Core PC and Brain status.",
                risk=ToolRisk.READ,
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                handler=self._get_pc_status,
            )
        )

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            spec.function_schema()
            for spec in self._tools.values()
            if spec.risk != ToolRisk.RESTRICTED
        ]

    def catalog(self) -> list[dict[str, str]]:
        return [
            {
                "name": spec.name,
                "risk": spec.risk.value,
                "description": spec.description,
            }
            for spec in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecution:
        spec = self._tools.get(name)
        if spec is None:
            return self._finish(
                ToolExecution(
                    tool=name,
                    risk=ToolRisk.RESTRICTED,
                    status="denied",
                    summary="Unknown tool",
                )
            )

        if spec.risk == ToolRisk.RESTRICTED:
            return self._finish(
                ToolExecution(
                    tool=name,
                    risk=spec.risk,
                    status="denied",
                    summary="Restricted tools cannot be executed by the AI provider.",
                )
            )

        if spec.risk == ToolRisk.CONFIRM:
            summary = self._confirmation_summary(spec, arguments)
            pending = _CONFIRMATIONS.put(name, arguments, summary)
            return self._finish(
                ToolExecution(
                    tool=name,
                    risk=spec.risk,
                    status="confirmation_required",
                    confirmation_id=pending.confirmation_id,
                    summary=pending.summary,
                )
            )

        return self._finish(self._run(spec, arguments))

    def confirm(self, confirmation_id: str) -> ToolExecution | None:
        pending = _CONFIRMATIONS.pop(confirmation_id)
        if pending is None:
            return None
        spec = self._tools.get(pending.tool)
        if spec is None or spec.risk != ToolRisk.CONFIRM:
            return self._finish(
                ToolExecution(
                    tool=pending.tool,
                    risk=ToolRisk.RESTRICTED,
                    status="denied",
                    summary="Pending action is no longer available.",
                )
            )
        return self._finish(self._run(spec, pending.arguments))

    def cancel(self, confirmation_id: str) -> ToolExecution | None:
        pending = _CONFIRMATIONS.pop(confirmation_id)
        if pending is None:
            return None
        spec = self._tools.get(pending.tool)
        risk = spec.risk if spec is not None else ToolRisk.CONFIRM
        return self._finish(
            ToolExecution(
                tool=pending.tool,
                risk=risk,
                status="cancelled",
                summary="Action cancelled by the user.",
            )
        )

    def pending_confirmations(self) -> list[dict[str, Any]]:
        return [action.to_dict() for action in _CONFIRMATIONS.list()]

    def recent_audit(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.audit.recent(limit=limit)

    def _confirmation_summary(self, spec: ToolSpec, arguments: dict[str, Any]) -> str:
        if spec.confirmation_summary is None:
            return f"Celeste wants to run {spec.name}."
        try:
            return spec.confirmation_summary(arguments)
        except Exception:
            return f"Celeste wants to run {spec.name}."

    def _run(self, spec: ToolSpec, arguments: dict[str, Any]) -> ToolExecution:
        try:
            output = spec.handler(arguments)
            return ToolExecution(
                tool=spec.name,
                risk=spec.risk,
                status="executed",
                output=output,
            )
        except (ValueError, ValidationError, BrainIndexError, NoteNotFoundError) as exc:
            return ToolExecution(
                tool=spec.name,
                risk=spec.risk,
                status="error",
                summary=str(exc),
            )
        except Exception as exc:  # Do not leak a provider-controlled exception upstream.
            return ToolExecution(
                tool=spec.name,
                risk=spec.risk,
                status="error",
                summary=f"Tool failed: {type(exc).__name__}",
            )

    def _finish(self, execution: ToolExecution) -> ToolExecution:
        try:
            self.audit.append(
                tool=execution.tool,
                risk=execution.risk.value,
                status=execution.status,
                confirmation_id=execution.confirmation_id,
                summary=execution.summary,
            )
        except Exception as exc:
            # Audit failure must not turn a successful Markdown write into a retry
            # that could duplicate user data.
            print(f"[Celeste] WARNING: tool audit write failed: {type(exc).__name__}")
        return execution

    def _search_memory(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        limit = int(arguments.get("limit", 5))
        limit = max(1, min(limit, 10))

        note_ids = self.index.search_ids(query, limit=limit)
        results: list[dict[str, Any]] = []
        for note_id in note_ids:
            try:
                note = self.storage.get(note_id)
            except NoteNotFoundError:
                continue
            if note.deleted:
                continue
            results.append(
                {
                    "id": note.id,
                    "title": note.title,
                    "content": note.content[:2000],
                    "type": note.type,
                    "tags": note.tags,
                    "updated_at": note.updated_at,
                }
            )
        return results

    def _create_note(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = NoteCreate.model_validate(
            {
                "title": arguments.get("title"),
                "content": arguments.get("content", ""),
                "type": arguments.get("type", "note"),
                "tags": arguments.get("tags", ["assistant"]),
            }
        )
        note = self.storage.create(payload)
        self._sync_index(note)
        return note.model_dump()

    def _update_note(self, arguments: dict[str, Any]) -> dict[str, Any]:
        note_id = str(arguments.get("note_id", "")).strip()
        if not note_id:
            raise ValueError("note_id is required")

        allowed = ("title", "content", "type", "tags")
        changes = {key: arguments[key] for key in allowed if key in arguments}
        if not changes:
            raise ValueError("At least one note field must be provided")

        payload = NoteUpdate.model_validate(changes)
        note = self.storage.update(note_id, payload)
        self._sync_index(note)
        return note.model_dump()

    def _delete_note(self, arguments: dict[str, Any]) -> dict[str, Any]:
        note_id = str(arguments.get("note_id", "")).strip()
        if not note_id:
            raise ValueError("note_id is required")
        note = self.storage.soft_delete(note_id)
        self._sync_index(note)
        return {
            "id": note.id,
            "title": note.title,
            "deleted": note.deleted,
            "version": note.version,
        }

    def _summarize_update_note(self, arguments: dict[str, Any]) -> str:
        note_id = str(arguments.get("note_id", "")).strip()
        note = self.storage.get(note_id)
        changed_fields = [key for key in ("title", "content", "type", "tags") if key in arguments]
        fields = ", ".join(changed_fields) or "unknown fields"
        return f"Modify note '{note.title}' ({fields})."

    def _summarize_delete_note(self, arguments: dict[str, Any]) -> str:
        note_id = str(arguments.get("note_id", "")).strip()
        note = self.storage.get(note_id)
        return f"Soft-delete note '{note.title}'."

    def _sync_index(self, note) -> None:
        try:
            self.index.upsert(note)
        except BrainIndexError as exc:
            print(f"[Celeste] WARNING: Brain index update failed after assistant note change: {exc}")

    def _get_pc_status(self, _: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": "Celeste",
            "version": self.settings.version,
            "status": "online",
            "os": platform.system(),
            "hostname": socket.gethostname(),
            "brain_ready": self.settings.brain_dir.exists(),
        }
