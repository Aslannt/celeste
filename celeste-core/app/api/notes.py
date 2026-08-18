from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.config import Settings
from app.models import Note, NoteCreate, NoteUpdate
from app.security import require_token
from app.services.index import BrainIndex, BrainIndexError
from app.services.storage import IdempotencyConflictError, MarkdownNoteStorage, NoteNotFoundError

router = APIRouter(
    prefix="/api/v1/notes",
    tags=["notes"],
    dependencies=[Depends(require_token)],
)


def _storage() -> MarkdownNoteStorage:
    return MarkdownNoteStorage(Settings.from_env().brain_dir)


def _index() -> BrainIndex:
    return BrainIndex(Settings.from_env().brain_dir)


def _sync_index(note: Note) -> None:
    try:
        _index().upsert(note)
    except BrainIndexError as exc:
        # Markdown is the source of truth. An index problem must never make a
        # successful note write look like a failed write to a client.
        print(f"[Celeste] WARNING: Brain index update failed: {exc}")


@router.get("", response_model=list[Note])
def list_notes(include_deleted: bool = Query(default=False)) -> list[Note]:
    return _storage().list(include_deleted=include_deleted)


@router.get("/search", response_model=list[Note])
def search_notes(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[Note]:
    storage = _storage()
    try:
        note_ids = _index().search_ids(q, limit=limit)
    except BrainIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    notes: list[Note] = []
    for note_id in note_ids:
        try:
            note = storage.get(note_id)
        except NoteNotFoundError:
            continue
        if not note.deleted:
            notes.append(note)
    return notes


@router.post("/index/rebuild")
def rebuild_note_index() -> dict[str, int]:
    storage = _storage()
    try:
        indexed = _index().rebuild(storage.list(include_deleted=False))
    except BrainIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {"indexed": indexed}


@router.post("", response_model=Note, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    x_celeste_idempotency_key: str | None = Header(default=None, max_length=200),
) -> Note:
    idempotency_key = x_celeste_idempotency_key.strip() if x_celeste_idempotency_key else None
    try:
        note = _storage().create(payload, idempotency_key=idempotency_key or None)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already exists with different note content",
        ) from exc
    _sync_index(note)
    return note


@router.get("/{note_id}", response_model=Note)
def get_note(note_id: str) -> Note:
    try:
        return _storage().get(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc


@router.put("/{note_id}", response_model=Note)
def update_note(note_id: str, payload: NoteUpdate) -> Note:
    try:
        note = _storage().update(note_id, payload)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    _sync_index(note)
    return note


@router.delete("/{note_id}", response_model=Note)
def delete_note(note_id: str) -> Note:
    try:
        note = _storage().soft_delete(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    _sync_index(note)
    return note
