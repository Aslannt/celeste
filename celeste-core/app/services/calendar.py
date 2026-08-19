from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.services.reminders import parse_instant

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
]


class CalendarError(ValueError):
    pass


class CalendarNotConnectedError(CalendarError):
    pass


class GoogleCalendarClient:
    """Narrow Google Calendar boundary for Celeste.

    The first Calendar increment intentionally targets only the owner's primary
    calendar and does not support attendees. That prevents a model-created event
    from emailing or inviting third parties. Read event text is marked as
    untrusted external content before it can reach an AI provider.
    """

    def __init__(self, credentials_file: Path, token_file: Path):
        self.credentials_file = credentials_file
        self.token_file = token_file

    def status(self, enabled: bool) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "credentials_present": self.credentials_file.exists(),
            "authorized": self.token_file.exists(),
            "scopes": list(CALENDAR_SCOPES),
            "calendar_id": "primary",
            "attendees_supported": False,
        }

    def authorize_interactive(self) -> dict[str, Any]:
        if not self.credentials_file.exists():
            raise CalendarNotConnectedError(
                f"Google OAuth credentials file not found: {self.credentials_file}"
            )
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise CalendarError("Google OAuth dependencies are not installed") from exc

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_file),
            CALENDAR_SCOPES,
        )
        credentials = flow.run_local_server(port=0)
        self._save_credentials(credentials)
        return {
            "authorized": True,
            "scopes": list(CALENDAR_SCOPES),
        }

    def list_upcoming(self, *, limit: int = 10, days: int = 14) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 20))
        days = max(1, min(int(days), 90))
        now = datetime.now(timezone.utc)
        response = self._execute(
            self._service()
            .events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat().replace("+00:00", "Z"),
                timeMax=(now + timedelta(days=days)).isoformat().replace("+00:00", "Z"),
                maxResults=limit,
                singleEvents=True,
                orderBy="startTime",
                showDeleted=False,
            )
        )
        return [
            self._event(item)
            for item in response.get("items", []) or []
            if isinstance(item, dict)
        ]

    def get_event(self, event_id: str) -> dict[str, Any]:
        event_id = self._required(event_id, "event_id")
        event = self._execute(
            self._service().events().get(calendarId="primary", eventId=event_id)
        )
        return self._event(event)

    def event_snapshot(self, event_id: str) -> dict[str, Any]:
        event_id = self._required(event_id, "event_id")
        event = self._execute(
            self._service().events().get(calendarId="primary", eventId=event_id)
        )
        result = self._event(event)
        result["etag"] = str(event.get("etag", ""))
        return result

    def create_event(
        self,
        *,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        summary = self._required(summary, "summary")
        start_dt, end_dt = self._validated_window(start, end)
        body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
        }
        if description.strip():
            body["description"] = description.strip()[:8000]
        if location.strip():
            body["location"] = location.strip()[:1000]

        event = self._execute(
            self._service().events().insert(
                calendarId="primary",
                body=body,
                sendUpdates="none",
            )
        )
        result = self._event(event)
        result["created"] = True
        return result

    def update_event(
        self,
        *,
        event_id: str,
        expected_etag: str,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
        event_id = self._required(event_id, "event_id")
        expected_etag = self._required(expected_etag, "expected_etag")
        body: dict[str, Any] = {}
        if summary is not None:
            body["summary"] = self._required(summary, "summary")
        if description is not None:
            body["description"] = description.strip()[:8000]
        if location is not None:
            body["location"] = location.strip()[:1000]
        if (start is None) != (end is None):
            raise CalendarError("start and end must be updated together")
        if start is not None and end is not None:
            start_dt, end_dt = self._validated_window(start, end)
            body["start"] = {"dateTime": start_dt.isoformat()}
            body["end"] = {"dateTime": end_dt.isoformat()}
        if not body:
            raise CalendarError("At least one event field must be provided")

        request = self._service().events().patch(
            calendarId="primary",
            eventId=event_id,
            body=body,
            sendUpdates="none",
        )
        request.headers["If-Match"] = expected_etag
        event = self._execute(request, stale_guard=True)
        result = self._event(event)
        result["updated"] = True
        return result

    def delete_event(self, *, event_id: str, expected_etag: str) -> dict[str, Any]:
        event_id = self._required(event_id, "event_id")
        expected_etag = self._required(expected_etag, "expected_etag")
        request = self._service().events().delete(
            calendarId="primary",
            eventId=event_id,
            sendUpdates="none",
        )
        request.headers["If-Match"] = expected_etag
        self._execute(request, stale_guard=True)
        return {
            "event_id": event_id,
            "deleted": True,
        }

    @staticmethod
    def _required(value: str, field: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise CalendarError(f"{field} is required")
        if "\r" in cleaned or "\n" in cleaned:
            raise CalendarError(f"Invalid newline in {field}")
        return cleaned

    @staticmethod
    def _validated_window(start: str, end: str) -> tuple[datetime, datetime]:
        start_dt = parse_instant(start)
        end_dt = parse_instant(end)
        if end_dt <= start_dt:
            raise CalendarError("end must be after start")
        return start_dt, end_dt

    @staticmethod
    def _event(event: dict[str, Any]) -> dict[str, Any]:
        start = event.get("start") or {}
        end = event.get("end") or {}
        return {
            "id": str(event.get("id", "")),
            "summary": str(event.get("summary", "")) or "(sin titulo)",
            "description": str(event.get("description", ""))[:8000],
            "location": str(event.get("location", ""))[:1000],
            "start": str(start.get("dateTime") or start.get("date") or ""),
            "end": str(end.get("dateTime") or end.get("date") or ""),
            "status": str(event.get("status", "")),
            "html_link": str(event.get("htmlLink", "")),
            "untrusted_external_content": True,
        }

    def _credentials(self):
        if not self.token_file.exists():
            raise CalendarNotConnectedError(
                "Google Calendar has not been authorized yet. Run the local Calendar authorization helper."
            )
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise CalendarError("Google authentication dependencies are not installed") from exc

        try:
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file),
                CALENDAR_SCOPES,
            )
        except Exception as exc:
            raise CalendarNotConnectedError("Could not read the Calendar OAuth token") from exc

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as exc:
                raise CalendarNotConnectedError("Could not refresh the Calendar OAuth token") from exc
            self._save_credentials(credentials)

        if not credentials.valid:
            raise CalendarNotConnectedError(
                "Calendar authorization is invalid or expired. Re-run the authorization helper."
            )
        return credentials

    def _service(self):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise CalendarError("Google API client dependency is not installed") from exc
        try:
            return build(
                "calendar",
                "v3",
                credentials=self._credentials(),
                cache_discovery=False,
            )
        except CalendarError:
            raise
        except Exception as exc:
            raise CalendarError(f"Could not initialize Calendar API: {type(exc).__name__}") from exc

    @staticmethod
    def _execute(request, *, stale_guard: bool = False):
        try:
            return request.execute()
        except Exception as exc:
            response = getattr(exc, "resp", None)
            if stale_guard and getattr(response, "status", None) == 412:
                raise CalendarError(
                    "Calendar event changed after confirmation was requested. Nothing was changed; request a new confirmation."
                ) from exc
            raise CalendarError(f"Calendar API request failed: {type(exc).__name__}") from exc

    def _save_credentials(self, credentials) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        try:
            os.chmod(self.token_file, 0o600)
        except OSError:
            pass
