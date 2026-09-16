from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import Settings
from app.services.notifications import NotificationStore
from app.services.reminder_monitor import ReminderMonitor
from app.services.reminders import ReminderError, ReminderStore
from app.services.tools import ToolRouter


def _configure(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", "reminder-test-token")
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    monkeypatch.setenv("CELESTE_GMAIL_ENABLED", "false")
    monkeypatch.setenv("CELESTE_CALENDAR_ENABLED", "false")
    monkeypatch.setenv("CELESTE_CALENDAR_TIME_ZONE", "America/Bogota")
    monkeypatch.setenv("CELESTE_REMINDER_POLL_SECONDS", "30")
    return Settings.from_env()


def _future(minutes: int = 30) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def _past(minutes: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def test_reminder_store_persists_and_lists_future_reminders(tmp_path):
    store = ReminderStore(tmp_path / "brain")
    created = store.create(
        title="Tomar medicamento",
        due_at=_future(),
        message="Una tableta",
    )

    reloaded = ReminderStore(tmp_path / "brain").list()
    assert len(reloaded) == 1
    assert reloaded[0]["id"] == created["id"]
    assert reloaded[0]["title"] == "Tomar medicamento"
    assert reloaded[0]["fired_at"] is None


def test_reminder_store_rejects_past_due_time(tmp_path):
    store = ReminderStore(tmp_path / "brain")
    try:
        store.create(title="Ya pasó", due_at=_past())
    except ReminderError as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError("past reminder should fail")


def test_reminder_monitor_creates_notification_once(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    store = ReminderStore(settings.brain_dir)

    # Store.create intentionally rejects past times; write one future reminder and
    # then use mark-free persisted data with a controlled due() clock.
    reminder = store.create(title="Prueba", due_at=_future(minutes=1), message="Avisar")
    due_at = datetime.now(UTC) + timedelta(minutes=2)
    assert store.due(now=due_at)[0]["id"] == reminder["id"]

    original_due = store.due
    monitor = ReminderMonitor(settings)
    monitor.reminders = store
    monitor.reminders.due = lambda limit=100: original_due(now=due_at, limit=limit)  # type: ignore[method-assign]

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert first.due_seen == 1
    assert first.notifications_created == 1
    assert second.due_seen == 0
    assert second.notifications_created == 0

    notices = NotificationStore(settings.brain_dir).list(include_seen=True)
    assert len(notices) == 1
    assert notices[0]["source"] == "reminder"
    assert notices[0]["kind"] == "due_reminder"
    assert notices[0]["metadata"]["reminder_id"] == reminder["id"]


def test_reminder_store_update_changes_title_due_at_and_message(tmp_path):
    store = ReminderStore(tmp_path / "brain")
    created = store.create(title="Sacar el pollo", due_at=_future(minutes=120))

    updated = store.update(
        created["id"],
        title="Sacar el pollo del horno",
        due_at=_future(minutes=2),
        message="Ya casi",
    )

    assert updated["title"] == "Sacar el pollo del horno"
    assert updated["message"] == "Ya casi"
    reloaded = ReminderStore(tmp_path / "brain").get(created["id"])
    assert reloaded["due_at"] == updated["due_at"]
    assert reloaded["due_at"] != created["due_at"]


def test_reminder_store_update_rejects_past_due_at(tmp_path):
    store = ReminderStore(tmp_path / "brain")
    created = store.create(title="Prueba", due_at=_future())
    try:
        store.update(created["id"], due_at=_past())
    except ReminderError as exc:
        assert "future" in str(exc)
    else:
        raise AssertionError("past due_at should fail")


def test_reminder_store_update_rejects_cancelled_reminder(tmp_path):
    store = ReminderStore(tmp_path / "brain")
    created = store.create(title="Prueba", due_at=_future())
    store.cancel(created["id"])
    try:
        store.update(created["id"], title="Otro titulo")
    except ReminderError as exc:
        assert "cancel" in str(exc).lower()
    else:
        raise AssertionError("updating a cancelled reminder should fail")


def test_reminder_store_update_missing_id_returns_none(tmp_path):
    store = ReminderStore(tmp_path / "brain")
    assert store.update("does-not-exist", title="x") is None


def test_reminder_tools_have_expected_risk_levels(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    router = ToolRouter(settings)
    tools = {item["name"]: item["risk"] for item in router.catalog()}

    assert tools["list_reminders"] == "READ"
    assert tools["create_reminder"] == "SAFE_WRITE"
    assert tools["update_reminder"] == "SAFE_WRITE"
    assert tools["complete_reminder"] == "SAFE_WRITE"
    assert tools["cancel_reminder"] == "CONFIRM"


def test_update_reminder_tool_executes_immediately(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    router = ToolRouter(settings)
    created = router.execute(
        "create_reminder",
        {"title": "Sacar el pollo", "due_at": _future(minutes=120)},
    )
    reminder_id = created.output["id"]

    result = router.execute(
        "update_reminder",
        {"reminder_id": reminder_id, "due_at": _future(minutes=2)},
    )

    assert result.status == "executed"
    assert result.output["due_at"] != created.output["due_at"]
    assert router.reminders.get(reminder_id)["due_at"] == result.output["due_at"]


def test_cancel_reminder_waits_for_confirmation(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    router = ToolRouter(settings)
    created = router.execute(
        "create_reminder",
        {
            "title": "Prueba cancelación",
            "due_at": _future(),
        },
    )
    reminder_id = created.output["id"]

    pending = router.execute("cancel_reminder", {"reminder_id": reminder_id})
    assert pending.status == "confirmation_required"
    assert router.reminders.get(reminder_id)["cancelled_at"] is None

    cancelled = router.cancel(pending.confirmation_id or "")
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert router.reminders.get(reminder_id)["cancelled_at"] is None

    pending = router.execute("cancel_reminder", {"reminder_id": reminder_id})
    confirmed = router.confirm(pending.confirmation_id or "")
    assert confirmed is not None
    assert confirmed.status == "executed"
    assert confirmed.output["cancelled_at"] is not None
