from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ReminderError(ValueError):
    pass


@dataclass(frozen=True)
class ReminderPollResult:
    due_seen: int
    notifications_created: int

    def to_dict(self) -> dict[str, int]:
        return {
            "due_seen": self.due_seen,
            "notifications_created": self.notifications_created,
        }


class ReminderStore:
    """Durable one-shot reminders stored locally inside Celeste Brain metadata."""

    def __init__(self, brain_dir: Path):
        self.path = brain_dir / ".celeste" / "reminders.json"
        self._lock = threading.RLock()

    def create(
        self,
        *,
        title: str,
        due_at: str,
        message: str | None = None,
        time_zone: str = "America/Bogota",
    ) -> dict[str, Any]:
        title = title.strip()
        if not title:
            raise ReminderError("title is required")
        due = _parse_due_at(due_at, time_zone)
        now = datetime.now(UTC)
        if due <= now:
            raise ReminderError("due_at must be in the future")

        reminder = {
            "id": str(uuid4()),
            "title": title,
            "message": str(message or "").strip(),
            "due_at": due.isoformat().replace("+00:00", "Z"),
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "fired_at": None,
            "done_at": None,
            "cancelled_at": None,
        }
        with self._lock:
            items = self._read()
            items.append(reminder)
            self._write(items)
        return dict(reminder)

    def list(
        self,
        *,
        include_done: bool = False,
        include_cancelled: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._lock:
            items = self._read()
        filtered = [
            item
            for item in items
            if (include_done or not item.get("done_at"))
            and (include_cancelled or not item.get("cancelled_at"))
        ]
        filtered.sort(key=lambda item: str(item.get("due_at", "")))
        return [dict(item) for item in filtered[:limit]]

    def get(self, reminder_id: str) -> dict[str, Any] | None:
        reminder_id = reminder_id.strip()
        with self._lock:
            for item in self._read():
                if item.get("id") == reminder_id:
                    return dict(item)
        return None

    def mark_done(self, reminder_id: str) -> dict[str, Any] | None:
        return self._stamp(reminder_id, "done_at")

    def cancel(self, reminder_id: str) -> dict[str, Any] | None:
        return self._stamp(reminder_id, "cancelled_at")

    def due(self, *, now: datetime | None = None, limit: int = 100) -> list[dict[str, Any]]:
        instant = (now or datetime.now(UTC)).astimezone(UTC)
        result: list[dict[str, Any]] = []
        with self._lock:
            for item in self._read():
                if item.get("done_at") or item.get("cancelled_at") or item.get("fired_at"):
                    continue
                due_at = _parse_utc(str(item.get("due_at", "")))
                if due_at <= instant:
                    result.append(dict(item))
                if len(result) >= max(1, min(int(limit), 200)):
                    break
        return result

    def mark_fired(self, reminder_id: str, *, when: datetime | None = None) -> dict[str, Any] | None:
        return self._stamp(
            reminder_id,
            "fired_at",
            when=(when or datetime.now(UTC)).astimezone(UTC),
        )

    def _stamp(
        self,
        reminder_id: str,
        field: str,
        *,
        when: datetime | None = None,
    ) -> dict[str, Any] | None:
        reminder_id = reminder_id.strip()
        if not reminder_id:
            raise ReminderError("reminder_id is required")
        stamp = (when or datetime.now(UTC)).astimezone(UTC).isoformat().replace("+00:00", "Z")
        with self._lock:
            items = self._read()
            for item in items:
                if item.get("id") == reminder_id:
                    item[field] = stamp
                    self._write(items)
                    return dict(item)
        return None

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReminderError("Could not read local reminder store") from exc
        if not isinstance(raw, list):
            raise ReminderError("Local reminder store has an invalid format")
        return [dict(item) for item in raw if isinstance(item, dict)]

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        payload = json.dumps(items, ensure_ascii=False, indent=2) + "\n"
        try:
            temp.write_text(payload, encoding="utf-8")
            os.replace(temp, self.path)
        except OSError as exc:
            raise ReminderError("Could not persist local reminder store") from exc


def _parse_due_at(value: str, time_zone: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ReminderError("due_at is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ReminderError("due_at must be an ISO-8601 date/time") from exc
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(time_zone))
        except ZoneInfoNotFoundError as exc:
            raise ReminderError(f"Unknown time zone: {time_zone}") from exc
    return parsed.astimezone(UTC)


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ReminderError("Stored reminder contains invalid due_at") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
