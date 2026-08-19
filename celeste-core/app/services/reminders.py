from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.notifications import NotificationStore

_REMINDER_LOCK = threading.RLock()
_ALLOWED_STATUSES = {"scheduled", "fired", "cancelled"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_instant(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("due_at is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("due_at must be a valid ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("due_at must include a timezone offset")
    return parsed.astimezone(timezone.utc)


class ReminderStoreError(RuntimeError):
    pass


class ReminderNotFoundError(ValueError):
    pass


class ReminderStore:
    """Persistent scheduler state for Celeste reminders.

    Reminders are operational state, not Brain memories. They live in a local
    SQLite database under `.celeste` and survive Core restarts.
    """

    def __init__(self, brain_dir: Path):
        self.path = brain_dir / ".celeste" / "reminders.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with _REMINDER_LOCK:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reminders (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        due_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        fired_at TEXT
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_reminders_status_due ON reminders(status, due_at)"
                )
                connection.commit()
            except sqlite3.Error as exc:
                raise ReminderStoreError(f"Could not initialize reminders: {exc}") from exc
            finally:
                connection.close()

    def create(
        self,
        *,
        title: str,
        due_at: str,
        detail: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        title = title.strip()
        detail = detail.strip()
        if not title:
            raise ValueError("title is required")
        due = parse_instant(due_at)
        current = (now or _utc_now()).astimezone(timezone.utc)
        if due <= current:
            raise ValueError("due_at must be in the future")

        reminder_id = str(uuid4())
        created = _iso_utc(current)
        with _REMINDER_LOCK:
            self.initialize()
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO reminders(
                        id, title, detail, due_at, status, created_at, updated_at, fired_at
                    ) VALUES (?, ?, ?, ?, 'scheduled', ?, ?, NULL)
                    """,
                    (
                        reminder_id,
                        title[:300],
                        detail[:2000],
                        _iso_utc(due),
                        created,
                        created,
                    ),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise ReminderStoreError(f"Could not create reminder: {exc}") from exc
            finally:
                connection.close()
        return self.get(reminder_id)

    def get(self, reminder_id: str) -> dict[str, Any]:
        reminder_id = reminder_id.strip()
        if not reminder_id:
            raise ValueError("reminder_id is required")
        self.initialize()
        with _REMINDER_LOCK:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT * FROM reminders WHERE id = ?",
                    (reminder_id,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise ReminderStoreError(f"Could not read reminder: {exc}") from exc
            finally:
                connection.close()
        if row is None:
            raise ReminderNotFoundError("Reminder not found")
        return self._row(row)

    def list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.initialize()
        limit = max(1, min(int(limit), 200))
        params: list[Any] = []
        where = ""
        if status is not None:
            normalized = status.strip().lower()
            if normalized not in _ALLOWED_STATUSES:
                raise ValueError("status must be scheduled, fired or cancelled")
            where = "WHERE status = ?"
            params.append(normalized)
        params.append(limit)
        sql = (
            "SELECT * FROM reminders "
            + where
            + " ORDER BY CASE WHEN status = 'scheduled' THEN 0 ELSE 1 END, due_at ASC LIMIT ?"
        )
        with _REMINDER_LOCK:
            connection = self._connect()
            try:
                rows = connection.execute(sql, params).fetchall()
                return [self._row(row) for row in rows]
            except sqlite3.Error as exc:
                raise ReminderStoreError(f"Could not list reminders: {exc}") from exc
            finally:
                connection.close()

    def cancel(self, reminder_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        current = _iso_utc((now or _utc_now()).astimezone(timezone.utc))
        with _REMINDER_LOCK:
            reminder = self.get(reminder_id)
            if reminder["status"] != "scheduled":
                raise ValueError(f"Reminder is already {reminder['status']}")
            connection = self._connect()
            try:
                connection.execute(
                    "UPDATE reminders SET status = 'cancelled', updated_at = ? WHERE id = ?",
                    (current, reminder_id),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise ReminderStoreError(f"Could not cancel reminder: {exc}") from exc
            finally:
                connection.close()
        return self.get(reminder_id)

    def reschedule(
        self,
        reminder_id: str,
        *,
        due_at: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        due = parse_instant(due_at)
        current_dt = (now or _utc_now()).astimezone(timezone.utc)
        if due <= current_dt:
            raise ValueError("due_at must be in the future")
        with _REMINDER_LOCK:
            reminder = self.get(reminder_id)
            if reminder["status"] != "scheduled":
                raise ValueError(f"Reminder is already {reminder['status']}")
            connection = self._connect()
            try:
                connection.execute(
                    "UPDATE reminders SET due_at = ?, updated_at = ? WHERE id = ?",
                    (_iso_utc(due), _iso_utc(current_dt), reminder_id),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise ReminderStoreError(f"Could not reschedule reminder: {exc}") from exc
            finally:
                connection.close()
        return self.get(reminder_id)

    def due(self, *, now: datetime | None = None, limit: int = 100) -> list[dict[str, Any]]:
        self.initialize()
        current = _iso_utc((now or _utc_now()).astimezone(timezone.utc))
        limit = max(1, min(int(limit), 500))
        with _REMINDER_LOCK:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM reminders
                    WHERE status = 'scheduled' AND due_at <= ?
                    ORDER BY due_at ASC
                    LIMIT ?
                    """,
                    (current, limit),
                ).fetchall()
                return [self._row(row) for row in rows]
            except sqlite3.Error as exc:
                raise ReminderStoreError(f"Could not read due reminders: {exc}") from exc
            finally:
                connection.close()

    def mark_fired(self, reminder_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        fired = _iso_utc((now or _utc_now()).astimezone(timezone.utc))
        self.initialize()
        with _REMINDER_LOCK:
            connection = self._connect()
            try:
                cursor = connection.execute(
                    """
                    UPDATE reminders
                    SET status = 'fired', fired_at = ?, updated_at = ?
                    WHERE id = ? AND status = 'scheduled'
                    """,
                    (fired, fired, reminder_id),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                raise ReminderStoreError(f"Could not mark reminder fired: {exc}") from exc
            finally:
                connection.close()
        if cursor.rowcount == 0:
            reminder = self.get(reminder_id)
            if reminder["status"] != "fired":
                raise ValueError(f"Reminder is already {reminder['status']}")
            return reminder
        return self.get(reminder_id)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "detail": str(row["detail"]),
            "due_at": str(row["due_at"]),
            "status": str(row["status"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "fired_at": str(row["fired_at"]) if row["fired_at"] is not None else None,
        }


class ReminderScheduler:
    """Turns due persistent reminders into deduplicated local notifications."""

    def __init__(self, brain_dir: Path):
        self.reminders = ReminderStore(brain_dir)
        self.notifications = NotificationStore(brain_dir)

    def poll_once(self, *, now: datetime | None = None) -> dict[str, int]:
        current = (now or _utc_now()).astimezone(timezone.utc)
        due = self.reminders.due(now=current)
        created = 0
        fired = 0
        for reminder in due:
            added = self.notifications.add_once(
                source="reminder",
                kind="scheduled_reminder",
                external_id=str(reminder["id"]),
                title=str(reminder["title"]),
                detail=str(reminder["detail"]) or "Recordatorio de Celeste",
                metadata={
                    "reminder_id": str(reminder["id"]),
                    "due_at": str(reminder["due_at"]),
                },
            )
            if added:
                created += 1
            # If the notification already exists after a crash/restart, add_once
            # returns False. Marking fired here still closes the durable reminder.
            self.reminders.mark_fired(str(reminder["id"]), now=current)
            fired += 1
        return {
            "due_seen": len(due),
            "notifications_created": created,
            "reminders_fired": fired,
        }
