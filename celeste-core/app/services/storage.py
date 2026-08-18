from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from app.models import Note, NoteCreate, NoteUpdate

_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:60] or "note"


def _normalize_tags(tags: list[str]) -> list[str]:
    return sorted(set(tag.strip() for tag in tags if tag.strip()))


class NoteNotFoundError(KeyError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class MarkdownNoteStorage:
    def __init__(self, brain_dir: Path):
        self.brain_dir = brain_dir
        self.notes_dir = brain_dir / "notes"
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def _find_path(self, note_id: str) -> Path:
        matches = list(self.notes_dir.glob(f"{note_id}-*.md"))
        if not matches:
            raise NoteNotFoundError(note_id)
        return matches[0]

    @staticmethod
    def _serialize(note: Note) -> str:
        metadata = note.model_dump(exclude={"content"}, exclude_none=True)
        frontmatter = yaml.safe_dump(
            metadata,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()
        body = note.content.rstrip()
        return f"---\n{frontmatter}\n---\n\n# {note.title}\n\n{body}\n"

    @staticmethod
    def _deserialize(text: str) -> Note:
        if not text.startswith("---\n"):
            raise ValueError("Invalid Celeste note: missing YAML frontmatter")
        _, frontmatter, body = text.split("---", 2)
        metadata = yaml.safe_load(frontmatter) or {}
        body = body.lstrip("\n")
        heading = f"# {metadata.get('title', '')}\n\n"
        if body.startswith(heading):
            body = body[len(heading):]
        metadata["content"] = body.rstrip("\n")
        return Note.model_validate(metadata)

    def _find_by_idempotency_key(self, idempotency_key: str) -> Note | None:
        for path in self.notes_dir.glob("*.md"):
            try:
                note = self._deserialize(path.read_text(encoding="utf-8"))
            except (ValueError, TypeError, yaml.YAMLError):
                continue
            if note.idempotency_key == idempotency_key:
                return note
        return None

    @staticmethod
    def _matches_create_payload(note: Note, data: NoteCreate) -> bool:
        return (
            note.title == data.title.strip()
            and note.content == data.content
            and note.type == data.type
            and note.tags == _normalize_tags(data.tags)
        )

    def create(self, data: NoteCreate, idempotency_key: str | None = None) -> Note:
        with _LOCK:
            if idempotency_key:
                existing = self._find_by_idempotency_key(idempotency_key)
                if existing is not None:
                    if not self._matches_create_payload(existing, data):
                        raise IdempotencyConflictError(idempotency_key)
                    return existing

            now = _utc_now()
            note = Note(
                id=str(uuid4()),
                title=data.title.strip(),
                content=data.content,
                type=data.type,
                tags=_normalize_tags(data.tags),
                created_at=now,
                updated_at=now,
                version=1,
                deleted=False,
                idempotency_key=idempotency_key,
            )
            path = self.notes_dir / f"{note.id}-{_slugify(note.title)}.md"
            path.write_text(self._serialize(note), encoding="utf-8")
            return note

    def get(self, note_id: str) -> Note:
        with _LOCK:
            path = self._find_path(note_id)
            return self._deserialize(path.read_text(encoding="utf-8"))

    def list(self, include_deleted: bool = False) -> list[Note]:
        with _LOCK:
            notes: list[Note] = []
            for path in self.notes_dir.glob("*.md"):
                try:
                    note = self._deserialize(path.read_text(encoding="utf-8"))
                except (ValueError, TypeError, yaml.YAMLError):
                    continue
                if include_deleted or not note.deleted:
                    notes.append(note)
            return sorted(notes, key=lambda note: note.updated_at, reverse=True)

    def update(self, note_id: str, data: NoteUpdate) -> Note:
        with _LOCK:
            old_path = self._find_path(note_id)
            note = self._deserialize(old_path.read_text(encoding="utf-8"))
            changes = data.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "tags" and value is not None:
                    value = _normalize_tags(value)
                setattr(note, key, value)
            note.updated_at = _utc_now()
            note.version += 1
            new_path = self.notes_dir / f"{note.id}-{_slugify(note.title)}.md"
            new_path.write_text(self._serialize(note), encoding="utf-8")
            if new_path != old_path and old_path.exists():
                old_path.unlink()
            return note

    def soft_delete(self, note_id: str) -> Note:
        with _LOCK:
            note = self.get(note_id)
            if not note.deleted:
                note.deleted = True
                note.updated_at = _utc_now()
                note.version += 1
                path = self._find_path(note_id)
                path.write_text(self._serialize(note), encoding="utf-8")
            return note
