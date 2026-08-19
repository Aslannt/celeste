from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import Settings
from app.security import require_token
from app.services.reminder_monitor import ReminderMonitor
from app.services.reminders import ReminderError, ReminderStore

router = APIRouter(
    prefix="/api/v1/reminders",
    tags=["reminders"],
    dependencies=[Depends(require_token)],
)


class ReminderCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: str = Field(min_length=1, max_length=100)
    message: str | None = Field(default=None, max_length=4000)
    time_zone: str | None = Field(default=None, max_length=100)


def _store() -> ReminderStore:
    return ReminderStore(Settings.from_env().brain_dir)


@router.get("")
def list_reminders(
    include_done: bool = Query(default=False),
    include_cancelled: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, Any]]:
    try:
        return _store().list(
            include_done=include_done,
            include_cancelled=include_cancelled,
            limit=limit,
        )
    except ReminderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("")
def create_reminder(request: ReminderCreateRequest) -> dict[str, Any]:
    settings = Settings.from_env()
    try:
        return ReminderStore(settings.brain_dir).create(
            title=request.title,
            due_at=request.due_at,
            message=request.message,
            time_zone=request.time_zone or settings.calendar_time_zone,
        )
    except ReminderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/poll")
def poll_reminders() -> dict[str, int]:
    settings = Settings.from_env()
    try:
        return ReminderMonitor(settings).poll_once().to_dict()
    except ReminderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{reminder_id}/done")
def mark_reminder_done(reminder_id: str) -> dict[str, Any]:
    try:
        reminder = _store().mark_done(reminder_id)
    except ReminderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.post("/{reminder_id}/cancel")
def cancel_reminder(reminder_id: str) -> dict[str, Any]:
    try:
        reminder = _store().cancel(reminder_id)
    except ReminderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder
