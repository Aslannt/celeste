from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.assistant import router as assistant_router
from app.api.integrations import router as integrations_router
from app.api.notes import router as notes_router
from app.api.notifications import router as notifications_router
from app.api.status import router as status_router
from app.config import Settings
from app.services.gmail import GmailClient, GmailError
from app.services.gmail_monitor import GmailMonitor
from app.services.index import BrainIndex, BrainIndexError
from app.services.notifications import NotificationStoreError
from app.services.storage import MarkdownNoteStorage


async def _gmail_monitor_loop(settings: Settings) -> None:
    monitor = GmailMonitor(settings)
    while True:
        try:
            result = await asyncio.to_thread(monitor.poll_once)
            if result.notifications_created:
                print(
                    "[Celeste] Gmail monitor: "
                    f"{result.notifications_created} new notice(s) from {result.unread_seen} unread message(s)."
                )
        except (GmailError, NotificationStoreError) as exc:
            # Mail monitoring is optional. A Gmail outage/token problem must never
            # take down Brain, notes or the assistant itself.
            print(f"[Celeste] WARNING: Gmail monitor poll failed: {exc}")
        await asyncio.sleep(settings.gmail_poll_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = Settings.from_env()
    storage = MarkdownNoteStorage(settings.brain_dir)
    gmail_monitor_task: asyncio.Task[None] | None = None

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
        elif settings.gmail_poll_seconds > 0:
            gmail_monitor_task = asyncio.create_task(_gmail_monitor_loop(settings))
            print(f"[Celeste] Gmail notice monitor every {settings.gmail_poll_seconds}s.")
        else:
            print("[Celeste] Gmail automatic monitoring is disabled; manual/on-demand access still works.")

    if settings.api_token == "celeste-local-dev":
        print("[Celeste] WARNING: using development API token. LAN testing only.")

    try:
        yield
    finally:
        if gmail_monitor_task is not None:
            gmail_monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await gmail_monitor_task


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
app.include_router(notifications_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Celeste Core",
        "docs": "/docs",
        "status": "/api/v1/status",
        "assistant": "/api/v1/assistant/chat",
        "gmail": "/api/v1/integrations/gmail/status",
        "notifications": "/api/v1/notifications",
    }
