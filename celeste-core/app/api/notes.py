from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.config import Settings
from app.models import Note, NoteCreate, NoteUpdate
from app.security import require_token
from app.services.storage import IdempotencyConflictError, MarkdownNoteStorage, NoteNotFoundError

router = APIRouter(
    prefix="/api/v1/notes",
    tags=["notes"],
    dependencies=[Depends(require_token)],
)


def _storage() -> MarkdownNoteStorage:
    return MarkdownNoteStorage(Settings.from_env().brain_dir)


@router.get("", response_model=list[Note])
def list_notes(include_deleted: bool = Query(default=False)) -> list[Note]:
    return _storage().list(include_deleted=include_deleted)


@router.post("", response_model=Note, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    x_celeste_idempotency_key: str | None = Header(default=None, max_length=200),
) -> Note:
    idempotency_key = x_celeste_idempotency_key.strip() if x_celeste_idempotency_key else None
    try:
        return _storage().create(payload, idempotency_key=idempotency_key or None)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already exists with different note content",
        ) from exc


@router.get("/{note_id}", response_model=Note)
def get_note(note_id: str) -> Note:
    try:
        return _storage().get(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc


@router.put("/{note_id}", response_model=Note)
def update_note(note_id: str, payload: NoteUpdate) -> Note:
    try:
        return _storage().update(note_id, payload)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc


@router.delete("/{note_id}", response_model=Note)
def delete_note(note_id: str) -> Note:
    try:
        return _storage().soft_delete(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
