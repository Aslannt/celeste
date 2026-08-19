from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.assistant import router as assistant_router
from app.api.integrations import router as integrations_router
from app.api.notes import router as notes_router
from app.api.notifications import router as notifications_router
from app.api.reminders import router as reminders_router
from app.api.status import router as status_router
from app.config import Settings
from app.services.calendar import CalendarClient
from app.services.gmail import GmailClient, GmailError
from app.services.gmail_monitor import GmailMonitor
from app.services.index import BrainIndex, BrainIndexError
from app.services.notifications import NotificationStoreError
from app.services.reminder_monitor import ReminderMonitor
from app.services.reminders import ReminderError
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


async def _reminder_monitor_loop(settings: Settings) -> None:
    monitor = ReminderMonitor(settings)
    while True:
        try:
            result = await asyncio.to_thread(monitor.poll_once)
            if result.notifications_created:
                print(
                    "[Celeste] Reminder monitor: "
                    f"{result.notifications_created} due reminder notice(s)."
                )
        except (ReminderError, NotificationStoreError) as exc:
            # Reminders must never take down the rest of Celeste if their local
            # store is temporarily unavailable.
            print(f"[Celeste] WARNING: reminder monitor poll failed: {exc}")
        await asyncio.sleep(settings.reminder_poll_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = Settings.from_env()
    storage = MarkdownNoteStorage(settings.brain_dir)
    gmail_monitor_task: asyncio.Task[None] | None = None
    reminder_monitor_task: asyncio.Task[None] | None = None

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

    if settings.calendar_enabled:
        calendar = CalendarClient(
            settings.calendar_credentials_file,
            settings.calendar_token_file,
        )
        calendar_state = calendar.status(enabled=True)
        print(
            "[Celeste] Calendar integration enabled: "
            f"authorized={calendar_state['authorized']} credentials={calendar_state['credentials_present']}"
        )
        if not calendar_state["authorized"]:
            print("[Celeste] Calendar needs local OAuth authorization before calendar tools can run.")

    reminder_monitor_task = asyncio.create_task(_reminder_monitor_loop(settings))
    print(f"[Celeste] Local reminder monitor every {settings.reminder_poll_seconds}s.")

    if settings.api_token == "celeste-local-dev":
        print("[Celeste] WARNING: using development API token. LAN testing only.")

    try:
        yield
    finally:
        for task in (gmail_monitor_task, reminder_monitor_task):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


app = FastAPI(
    title="Celeste Core",
    version="0.4.2",
    description="Local core service for the Celeste personal assistant.",
    lifespan=lifespan,
)

app.include_router(status_router)
app.include_router(notes_router)
app.include_router(assistant_router)
app.include_router(integrations_router)
app.include_router(notifications_router)
app.include_router(reminders_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "Celeste Core",
        "docs": "/docs",
        "status": "/api/v1/status",
        "assistant": "/api/v1/assistant/chat",
        "gmail": "/api/v1/integrations/gmail/status",
        "calendar": "/api/v1/integrations/calendar/status",
        "reminders": "/api/v1/reminders",
        "notifications": "/api/v1/notifications",
    }
