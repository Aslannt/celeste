from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services.calendar import CalendarClient
from app.services.tools import ToolRouter


def _configure(tmp_path: Path, monkeypatch, enabled: bool = True) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", "calendar-test-token")
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    monkeypatch.setenv("CELESTE_GMAIL_ENABLED", "false")
    monkeypatch.setenv("CELESTE_CALENDAR_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("CELESTE_CALENDAR_ID", "primary")
    monkeypatch.setenv("CELESTE_CALENDAR_TIME_ZONE", "America/Bogota")
    monkeypatch.setenv(
        "CELESTE_CALENDAR_CREDENTIALS_FILE",
        str(tmp_path / "secrets" / "calendar-credentials.json"),
    )
    monkeypatch.setenv(
        "CELESTE_CALENDAR_TOKEN_FILE",
        str(tmp_path / "secrets" / "calendar-token.json"),
    )
    return Settings.from_env()


class FakeRequest:
    def __init__(self, value=None, callback=None):
        self.value = value
        self.callback = callback

    def execute(self):
        if self.callback is not None:
            return self.callback()
        return self.value


class FakeEvents:
    def __init__(self):
        self.items: dict[str, dict] = {
            "event-1": {
                "id": "event-1",
                "summary": "Evento existente",
                "description": "Datos externos",
                "status": "confirmed",
                "start": {"dateTime": "2026-08-20T10:00:00-05:00"},
                "end": {"dateTime": "2026-08-20T11:00:00-05:00"},
                "organizer": {"email": "owner@example.com"},
                "attendees": [{"email": "external@example.com"}],
            }
        }
        self.insert_calls: list[dict] = []
        self.patch_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self.list_calls: list[dict] = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest({"items": list(self.items.values())[: kwargs.get("maxResults", 10)]})

    def get(self, **kwargs):
        return FakeRequest(self.items[kwargs["eventId"]])

    def insert(self, **kwargs):
        self.insert_calls.append(kwargs)
        body = dict(kwargs["body"])
        event = {
            "id": "event-created",
            "status": "confirmed",
            **body,
        }
        self.items["event-created"] = event
        return FakeRequest(event)

    def patch(self, **kwargs):
        self.patch_calls.append(kwargs)
        event_id = kwargs["eventId"]
        self.items[event_id] = {**self.items[event_id], **kwargs["body"]}
        return FakeRequest(self.items[event_id])

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)

        def _delete():
            self.items.pop(kwargs["eventId"], None)
            return None

        return FakeRequest(callback=_delete)


class FakeService:
    def __init__(self):
        self.events_api = FakeEvents()

    def events(self):
        return self.events_api


def test_calendar_tools_are_disabled_by_default(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, enabled=False)
    router = ToolRouter(settings)
    names = {item["name"] for item in router.catalog()}
    assert "calendar_list_events" not in names
    assert "calendar_create_event" not in names


def test_calendar_tools_have_expected_risk_levels(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, enabled=True)
    router = ToolRouter(settings)
    tools = {item["name"]: item["risk"] for item in router.catalog()}

    assert tools["calendar_list_events"] == "READ"
    assert tools["calendar_get_event"] == "READ"
    assert tools["calendar_create_event"] == "SAFE_WRITE"
    assert tools["calendar_update_event"] == "CONFIRM"
    assert tools["calendar_delete_event"] == "CONFIRM"


def test_calendar_list_marks_event_content_untrusted(tmp_path):
    service = FakeService()
    client = CalendarClient(tmp_path / "credentials.json", tmp_path / "token.json")
    client._service = lambda: service  # type: ignore[method-assign]

    events = client.list_events(
        time_min="2026-08-20T00:00:00-05:00",
        limit=5,
    )

    assert service.events_api.list_calls[0]["calendarId"] == "primary"
    assert service.events_api.list_calls[0]["singleEvents"] is True
    assert events[0]["summary"] == "Evento existente"
    assert events[0]["untrusted_external_content"] is True
    assert events[0]["attendees"] == ["external@example.com"]


def test_calendar_create_event_never_adds_attendees_or_sends_updates(tmp_path):
    service = FakeService()
    client = CalendarClient(tmp_path / "credentials.json", tmp_path / "token.json")
    client._service = lambda: service  # type: ignore[method-assign]

    created = client.create_event(
        summary="Cita médica",
        start="2026-08-21T09:00:00-05:00",
        end="2026-08-21T10:00:00-05:00",
        time_zone="America/Bogota",
        reminder_minutes=30,
    )

    call = service.events_api.insert_calls[0]
    assert call["sendUpdates"] == "none"
    assert "attendees" not in call["body"]
    assert call["body"]["reminders"]["overrides"] == [
        {"method": "popup", "minutes": 30}
    ]
    assert created["summary"] == "Cita médica"


def test_calendar_update_and_delete_wait_for_confirmation(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, enabled=True)
    service = FakeService()
    router = ToolRouter(settings)
    assert router.calendar is not None
    router.calendar._service = lambda: service  # type: ignore[method-assign]

    pending_update = router.execute(
        "calendar_update_event",
        {"event_id": "event-1", "summary": "Evento actualizado"},
    )
    assert pending_update.status == "confirmation_required"
    assert service.events_api.patch_calls == []

    cancelled = router.cancel(pending_update.confirmation_id or "")
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert service.events_api.patch_calls == []

    pending_delete = router.execute("calendar_delete_event", {"event_id": "event-1"})
    assert pending_delete.status == "confirmation_required"
    assert service.events_api.delete_calls == []

    confirmed = router.confirm(pending_delete.confirmation_id or "")
    assert confirmed is not None
    assert confirmed.status == "executed"
    assert confirmed.output["deleted"] is True
    assert service.events_api.delete_calls[0]["sendUpdates"] == "none"
