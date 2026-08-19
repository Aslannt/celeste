from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.services.gmail import GmailClient
from app.services.notifications import NotificationStore


@dataclass(frozen=True)
class GmailPollResult:
    unread_seen: int
    notifications_created: int

    def to_dict(self) -> dict[str, int]:
        return {
            "unread_seen": self.unread_seen,
            "notifications_created": self.notifications_created,
        }


class GmailMonitor:
    """Convert unread Gmail metadata into local, deduplicated Celeste notices."""

    def __init__(self, settings: Settings):
        self.gmail = GmailClient(
            settings.gmail_credentials_file,
            settings.gmail_token_file,
        )
        self.notifications = NotificationStore(settings.brain_dir)

    def poll_once(self, limit: int = 10) -> GmailPollResult:
        messages = self.gmail.list_unread(limit=max(1, min(int(limit), 10)))
        created = 0
        for message in messages:
            message_id = str(message.get("id", "")).strip()
            if not message_id:
                continue
            subject = str(message.get("subject", "")).strip() or "(sin asunto)"
            sender = str(message.get("from", "")).strip() or "Remitente desconocido"
            if self.notifications.add_once(
                source="gmail",
                kind="unread_email",
                external_id=message_id,
                title=subject,
                detail=f"Correo de {sender}",
                metadata={
                    "message_id": message_id,
                    "thread_id": str(message.get("thread_id", "")),
                    "from": sender,
                },
            ):
                created += 1

        return GmailPollResult(
            unread_seen=len(messages),
            notifications_created=created,
        )
