from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings
from app.security import require_token
from app.services.notifications import NotificationStore, NotificationStoreError

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_token)],
)


def _store() -> NotificationStore:
    return NotificationStore(Settings.from_env().brain_dir)


@router.get("")
def list_notifications(
    include_seen: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    try:
        return _store().list(include_seen=include_seen, limit=limit)
    except NotificationStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/{notification_id}/seen")
def mark_notification_seen(notification_id: str) -> dict[str, bool]:
    try:
        updated = _store().mark_seen(notification_id)
    except NotificationStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"seen": True}


@router.delete("/{notification_id}")
def dismiss_notification(notification_id: str) -> dict[str, bool]:
    try:
        updated = _store().dismiss(notification_id)
    except NotificationStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"dismissed": True}
