from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.gmail_monitor import GmailMonitor
from app.services.notifications import NotificationStore

TOKEN = "notification-test-token"
HEADERS = {"X-Celeste-Token": TOKEN}


def _configure(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_GMAIL_ENABLED", "true")
    monkeypatch.setenv("CELESTE_GMAIL_POLL_SECONDS", "0")
    monkeypatch.setenv("CELESTE_GMAIL_CREDENTIALS_FILE", str(tmp_path / "credentials.json"))
    monkeypatch.setenv("CELESTE_GMAIL_TOKEN_FILE", str(tmp_path / "token.json"))
    return Settings.from_env()


def test_notification_store_deduplicates_external_events(tmp_path):
    store = NotificationStore(tmp_path / "brain")

    first = store.add_once(
        source="gmail",
        kind="unread_email",
        external_id="msg-1",
        title="Hola",
        detail="Correo de Ana",
        metadata={"message_id": "msg-1"},
    )
    duplicate = store.add_once(
        source="gmail",
        kind="unread_email",
        external_id="msg-1",
        title="Hola otra vez",
        detail="No debe duplicarse",
        metadata={"message_id": "msg-1"},
    )

    assert first is True
    assert duplicate is False
    notices = store.list()
    assert len(notices) == 1
    assert notices[0]["title"] == "Hola"


def test_gmail_monitor_creates_only_new_notices(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    monitor = GmailMonitor(settings)
    monitor.gmail.list_unread = lambda limit=10: [  # type: ignore[method-assign]
        {
            "id": "msg-1",
            "thread_id": "thread-1",
            "from": "Ana <ana@example.com>",
            "subject": "Reunion de manana",
            "snippet": "Sensitive snippet should not be persisted by monitor",
        },
        {
            "id": "msg-2",
            "thread_id": "thread-2",
            "from": "Luis <luis@example.com>",
            "subject": "Documento",
        },
    ]

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert first.unread_seen == 2
    assert first.notifications_created == 2
    assert second.notifications_created == 0

    notices = NotificationStore(settings.brain_dir).list()
    assert len(notices) == 2
    assert all("snippet" not in notice["metadata"] for notice in notices)


def test_notification_api_seen_and_dismiss_flow(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    store = NotificationStore(settings.brain_dir)
    store.add_once(
        source="gmail",
        kind="unread_email",
        external_id="msg-1",
        title="Correo de prueba",
        detail="Correo de test@example.com",
        metadata={"message_id": "msg-1"},
    )

    with TestClient(app) as client:
        listed = client.get("/api/v1/notifications", headers=HEADERS)
        assert listed.status_code == 200
        notice_id = listed.json()[0]["id"]

        seen = client.post(f"/api/v1/notifications/{notice_id}/seen", headers=HEADERS)
        assert seen.status_code == 200
        assert seen.json()["seen"] is True

        unseen = client.get("/api/v1/notifications", headers=HEADERS)
        assert unseen.json() == []

        including_seen = client.get(
            "/api/v1/notifications?include_seen=true",
            headers=HEADERS,
        )
        assert len(including_seen.json()) == 1

        dismissed = client.delete(f"/api/v1/notifications/{notice_id}", headers=HEADERS)
        assert dismissed.status_code == 200

        after = client.get(
            "/api/v1/notifications?include_seen=true",
            headers=HEADERS,
        )
        assert after.json() == []


def test_gmail_poll_interval_is_opt_in_and_clamped(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    assert settings.gmail_poll_seconds == 0

    monkeypatch.setenv("CELESTE_GMAIL_POLL_SECONDS", "10")
    assert Settings.from_env().gmail_poll_seconds == 60

    monkeypatch.setenv("CELESTE_GMAIL_POLL_SECONDS", "99999")
    assert Settings.from_env().gmail_poll_seconds == 3600
