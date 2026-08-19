from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import Settings
from app.security import require_token
from app.services.notifications import NotificationStoreError
from app.services.reminders import (
    ReminderNotFoundError,
    ReminderScheduler,
    ReminderStore,
    ReminderStoreError,
)


class ReminderCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(default="", max_length=2000)
    due_at: str = Field(min_length=1, max_length=100)


class ReminderRescheduleRequest(BaseModel):
    due_at: str = Field(min_length=1, max_length=100)


router = APIRouter(
    prefix="/api/v1/reminders",
    tags=["reminders"],
    dependencies=[Depends(require_token)],
)


def _store() -> ReminderStore:
    return ReminderStore(Settings.from_env().brain_dir)


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ReminderNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (ReminderStoreError, NotificationStoreError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("")
def list_reminders(
    state: Literal["scheduled", "fired", "cancelled"] | None = Query(default="scheduled"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, object]]:
    try:
        return _store().list(status=state, limit=limit)
    except (ValueError, ReminderStoreError) as exc:
        raise _translate_error(exc) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_reminder(payload: ReminderCreateRequest) -> dict[str, object]:
    try:
        return _store().create(
            title=payload.title,
            detail=payload.detail,
            due_at=payload.due_at,
        )
    except (ValueError, ReminderStoreError) as exc:
        raise _translate_error(exc) from exc


@router.post("/poll")
def poll_reminders() -> dict[str, int]:
    settings = Settings.from_env()
    try:
        return ReminderScheduler(settings.brain_dir).poll_once()
    except (ValueError, ReminderStoreError, NotificationStoreError) as exc:
        raise _translate_error(exc) from exc


@router.get("/{reminder_id}")
def get_reminder(reminder_id: str) -> dict[str, object]:
    try:
        return _store().get(reminder_id)
    except (ValueError, ReminderStoreError) as exc:
        raise _translate_error(exc) from exc


@router.post("/{reminder_id}/reschedule")
def reschedule_reminder(
    reminder_id: str,
    payload: ReminderRescheduleRequest,
) -> dict[str, object]:
    try:
        return _store().reschedule(reminder_id, due_at=payload.due_at)
    except (ValueError, ReminderStoreError) as exc:
        raise _translate_error(exc) from exc


@router.post("/{reminder_id}/cancel")
def cancel_reminder(reminder_id: str) -> dict[str, object]:
    try:
        return _store().cancel(reminder_id)
    except (ValueError, ReminderStoreError) as exc:
        raise _translate_error(exc) from exc
