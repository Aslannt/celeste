from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.security import require_token
from app.services.gmail import GmailClient

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
    return client.status(enabled=settings.gmail_enabled)
