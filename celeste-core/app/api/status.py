from __future__ import annotations

import platform
import socket
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import Settings

router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/status")
def status() -> dict[str, object]:
    settings = Settings.from_env()
    return {
        "name": "Celeste",
        "version": settings.version,
        "status": "online",
        "os": platform.system(),
        "hostname": socket.gethostname(),
        "brain_ready": settings.brain_dir.exists(),
        "time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
