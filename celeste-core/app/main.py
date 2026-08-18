from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.notes import router as notes_router
from app.api.status import router as status_router
from app.config import Settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = Settings.from_env()
    (settings.brain_dir / "notes").mkdir(parents=True, exist_ok=True)
    if settings.api_token == "celeste-local-dev":
        print("[Celeste] WARNING: using development API token. LAN testing only.")
    yield


app = FastAPI(
    title="Celeste Core",
    version="0.1.0",
    description="Local core service for the Celeste personal assistant.",
    lifespan=lifespan,
)

app.include_router(status_router)
app.include_router(notes_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Celeste Core",
        "docs": "/docs",
        "status": "/api/v1/status",
    }
