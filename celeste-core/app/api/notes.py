from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings
from app.models import Note, NoteCreate, NoteUpdate
from app.security import require_token
from app.services.storage import MarkdownNoteStorage, NoteNotFoundError

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
def create_note(payload: NoteCreate) -> Note:
    return _storage().create(payload)


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
