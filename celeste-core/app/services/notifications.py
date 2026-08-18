from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_NOTIFICATION_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class NotificationStoreError(RuntimeError):
    pass


class NotificationStore:
    """Persistent local feed for ephemeral Celeste notices.

    Notifications are not Celeste Brain memories and therefore do not become
    Markdown. They live in a small local SQLite database under `.celeste`.
    """

    def __init__(self, brain_dir: Path):
        self.path = brain_dir / ".celeste" / "notifications.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with _NOTIFICATION_LOCK:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notifications (
                        id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        external_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        seen INTEGER NOT NULL DEFAULT 0,
                        dismissed INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(source, kind, external_id)
                    )
                    """
                )
                connection.commit()
            except sqlite3.Error as exc:
                raise NotificationStoreError(f"Could not initialize notifications: {exc}") from exc
            finally:
                connection.close()

    def add_once(
        self,
        *,
        source: str,
        kind: str,
        external_id: str,
        title: str,
        detail: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        source = source.strip()
        kind = kind.strip()
        external_id = external_id.strip()
        if not source or not kind or not external_id:
            raise ValueError("source, kind and external_id are required")

        self.initialize()
        with _NOTIFICATION_LOCK:
            connection = self._connect()
            try:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO notifications(
                        id, source, kind, external_id, title, detail,
                        metadata_json, created_at, seen, dismissed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (
                        str(uuid4()),
                        source,
                        kind,
                        external_id,
                        title.strip()[:300],
                        detail.strip()[:1000],
                        json.dumps(metadata or {}, ensure_ascii=False),
                        _utc_now(),
                    ),
                )
                connection.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as exc:
                connection.rollback()
                raise NotificationStoreError(f"Could not add notification: {exc}") from exc
            finally:
                connection.close()

    def list(self, *, include_seen: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        self.initialize()
        limit = max(1, min(int(limit), 200))
        clauses = ["dismissed = 0"]
        if not include_seen:
            clauses.append("seen = 0")
        sql = (
            "SELECT * FROM notifications WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at DESC LIMIT ?"
        )

        with _NOTIFICATION_LOCK:
            connection = self._connect()
            try:
                rows = connection.execute(sql, (limit,)).fetchall()
                return [self._row(row) for row in rows]
            except sqlite3.Error as exc:
                raise NotificationStoreError(f"Could not list notifications: {exc}") from exc
            finally:
                connection.close()

    def mark_seen(self, notification_id: str) -> bool:
        return self._set_flag(notification_id, "seen")

    def dismiss(self, notification_id: str) -> bool:
        return self._set_flag(notification_id, "dismissed")

    def _set_flag(self, notification_id: str, column: str) -> bool:
        if column not in {"seen", "dismissed"}:
            raise ValueError("invalid notification flag")
        self.initialize()
        with _NOTIFICATION_LOCK:
            connection = self._connect()
            try:
                cursor = connection.execute(
                    f"UPDATE notifications SET {column} = 1 WHERE id = ?",
                    (notification_id,),
                )
                connection.commit()
                return cursor.rowcount == 1
            except sqlite3.Error as exc:
                connection.rollback()
                raise NotificationStoreError(f"Could not update notification: {exc}") from exc
            finally:
                connection.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        try:
            metadata = json.loads(str(row["metadata_json"]))
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "id": str(row["id"]),
            "source": str(row["source"]),
            "kind": str(row["kind"]),
            "external_id": str(row["external_id"]),
            "title": str(row["title"]),
            "detail": str(row["detail"]),
            "metadata": metadata,
            "created_at": str(row["created_at"]),
            "seen": bool(row["seen"]),
        }
