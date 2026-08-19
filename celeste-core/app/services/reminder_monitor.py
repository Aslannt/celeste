from __future__ import annotations

from app.config import Settings
from app.services.notifications import NotificationStore
from app.services.reminders import ReminderPollResult, ReminderStore


class ReminderMonitor:
    """Turn due local reminders into deduplicated Celeste notifications."""

    def __init__(self, settings: Settings):
        self.reminders = ReminderStore(settings.brain_dir)
        self.notifications = NotificationStore(settings.brain_dir)

    def poll_once(self) -> ReminderPollResult:
        due = self.reminders.due(limit=100)
        created = 0
        for reminder in due:
            reminder_id = str(reminder.get("id", "")).strip()
            if not reminder_id:
                continue
            title = str(reminder.get("title", "")).strip() or "Recordatorio"
            message = str(reminder.get("message", "")).strip()
            if self.notifications.add_once(
                source="reminder",
                kind="due_reminder",
                external_id=reminder_id,
                title=title,
                detail=message or "Recordatorio de Celeste",
                metadata={
                    "reminder_id": reminder_id,
                    "due_at": str(reminder.get("due_at", "")),
                },
            ):
                created += 1
            self.reminders.mark_fired(reminder_id)

        return ReminderPollResult(
            due_seen=len(due),
            notifications_created=created,
        )
