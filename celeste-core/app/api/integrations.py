from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings
from app.security import require_token
from app.services.calendar import CalendarClient, CalendarError
from app.services.gmail import GmailClient, GmailError
from app.services.gmail_monitor import GmailMonitor
from app.services.notifications import NotificationStoreError

router = APIRouter(
    prefix="/api/v1/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_token)],
)


@router.get("/gmail/status")
def gmail_status() -> dict[str, object]:
    settings = Settings.from_env()
    client = GmailClient(
        settings.gmail_credentials_file,
        settings.gmail_token_file,
    )
    result = client.status(enabled=settings.gmail_enabled)
    result["poll_seconds"] = settings.gmail_poll_seconds
    result["monitor_enabled"] = settings.gmail_enabled and settings.gmail_poll_seconds > 0
    return result


@router.post("/gmail/poll")
def poll_gmail() -> dict[str, int]:
    settings = Settings.from_env()
    if not settings.gmail_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Gmail integration is disabled",
        )
    try:
        return GmailMonitor(settings).poll_once().to_dict()
    except (GmailError, NotificationStoreError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/calendar/status")
def calendar_status() -> dict[str, object]:
    settings = Settings.from_env()
    client = CalendarClient(
        settings.calendar_credentials_file,
        settings.calendar_token_file,
    )
    result = client.status(enabled=settings.calendar_enabled)
    result["calendar_id"] = settings.calendar_id
    result["time_zone"] = settings.calendar_time_zone
    return result


@router.get("/calendar/events")
def calendar_events(
    time_min: str | None = Query(default=None),
    time_max: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=20),
) -> list[dict[str, object]]:
    settings = Settings.from_env()
    if not settings.calendar_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Calendar integration is disabled",
        )
    try:
        return CalendarClient(
            settings.calendar_credentials_file,
            settings.calendar_token_file,
        ).list_events(
            time_min=time_min,
            time_max=time_max,
            limit=limit,
            calendar_id=settings.calendar_id,
        )
    except CalendarError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
