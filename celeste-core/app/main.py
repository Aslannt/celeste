from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.assistant import router as assistant_router
from app.api.integrations import router as integrations_router
from app.api.notes import router as notes_router
from app.api.status import router as status_router
from app.config import Settings
from app.services.gmail import GmailClient
from app.services.index import BrainIndex, BrainIndexError
from app.services.storage import MarkdownNoteStorage


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = Settings.from_env()
    storage = MarkdownNoteStorage(settings.brain_dir)

    try:
        indexed = BrainIndex(settings.brain_dir).rebuild(storage.list(include_deleted=False))
        print(f"[Celeste] Brain index ready: {indexed} note(s) indexed.")
    except BrainIndexError as exc:
        # Search may be unavailable, but Markdown note storage must remain usable.
        print(f"[Celeste] WARNING: Brain index unavailable: {exc}")

    print(f"[Celeste] AI provider: {settings.llm_provider} ({settings.llm_model})")
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        print("[Celeste] WARNING: OPENAI_API_KEY is missing; assistant chat will be unavailable.")

    if settings.gmail_enabled:
        gmail = GmailClient(settings.gmail_credentials_file, settings.gmail_token_file)
        gmail_state = gmail.status(enabled=True)
        print(
            "[Celeste] Gmail integration enabled: "
            f"authorized={gmail_state['authorized']} credentials={gmail_state['credentials_present']}"
        )
        if not gmail_state["authorized"]:
            print("[Celeste] Gmail needs local OAuth authorization before mail tools can run.")

    if settings.api_token == "celeste-local-dev":
        print("[Celeste] WARNING: using development API token. LAN testing only.")
    yield


app = FastAPI(
    title="Celeste Core",
    version="0.4.1",
    description="Local core service for the Celeste personal assistant.",
    lifespan=lifespan,
)

app.include_router(status_router)
app.include_router(notes_router)
app.include_router(assistant_router)
app.include_router(integrations_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Celeste Core",
        "docs": "/docs",
        "status": "/api/v1/status",
        "assistant": "/api/v1/assistant/chat",
        "gmail": "/api/v1/integrations/gmail/status",
    }
