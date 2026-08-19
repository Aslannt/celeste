from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CalendarError(ValueError):
    pass


class CalendarNotConnectedError(CalendarError):
    pass


class CalendarClient:
    """Small Google Calendar API boundary for Celeste.

    OAuth tokens stay local to this service. Event titles/descriptions/locations may
    originate from invitations or other people, so returned event data is marked as
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
        }

    def authorize_interactive(self) -> dict[str, Any]:
        if not self.credentials_file.exists():
            raise CalendarNotConnectedError(
                f"Calendar OAuth credentials file not found: {self.credentials_file}"
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

    def list_events(
        self,
        *,
        time_min: str | None = None,
        time_max: str | None = None,
        limit: int = 10,
        calendar_id: str = "primary",
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 20))
        kwargs: dict[str, Any] = {
            "calendarId": calendar_id or "primary",
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": limit,
        }
        if time_min:
            kwargs["timeMin"] = time_min.strip()
        if time_max:
            kwargs["timeMax"] = time_max.strip()

        service = self._service()
        response = self._execute(service.events().list(**kwargs))
        return [
            self._normalize_event(event)
            for event in response.get("items", []) or []
            if isinstance(event, dict)
        ]

    def get_event(self, event_id: str, *, calendar_id: str = "primary") -> dict[str, Any]:
        event_id = event_id.strip()
        if not event_id:
            raise CalendarError("event_id is required")
        service = self._service()
        event = self._execute(
            service.events().get(
                calendarId=calendar_id or "primary",
                eventId=event_id,
            )
        )
        return self._normalize_event(event)

    def create_event(
        self,
        *,
        summary: str,
        start: str,
        end: str,
        time_zone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        reminder_minutes: int | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        summary = summary.strip()
        if not summary:
            raise CalendarError("summary is required")

        body: dict[str, Any] = {
            "summary": summary,
            "start": self._event_time(start, time_zone),
            "end": self._event_time(end, time_zone),
        }
        if description is not None:
            body["description"] = str(description)
        if location is not None:
            body["location"] = str(location)
        if reminder_minutes is not None:
            minutes = max(0, min(int(reminder_minutes), 40320))
            body["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": minutes}],
            }

        service = self._service()
        event = self._execute(
            service.events().insert(
                calendarId=calendar_id or "primary",
                body=body,
                sendUpdates="none",
            )
        )
        return self._normalize_event(event)

    def update_event(
        self,
        event_id: str,
        *,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        time_zone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        reminder_minutes: int | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        event_id = event_id.strip()
        if not event_id:
            raise CalendarError("event_id is required")

        body: dict[str, Any] = {}
        if summary is not None:
            cleaned = summary.strip()
            if not cleaned:
                raise CalendarError("summary cannot be empty")
            body["summary"] = cleaned
        if start is not None:
            body["start"] = self._event_time(start, time_zone)
        if end is not None:
            body["end"] = self._event_time(end, time_zone)
        if description is not None:
            body["description"] = str(description)
        if location is not None:
            body["location"] = str(location)
        if reminder_minutes is not None:
            minutes = max(0, min(int(reminder_minutes), 40320))
            body["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": minutes}],
            }
        if not body:
            raise CalendarError("at least one event field must be updated")

        service = self._service()
        event = self._execute(
            service.events().patch(
                calendarId=calendar_id or "primary",
                eventId=event_id,
                body=body,
                sendUpdates="none",
            )
        )
        return self._normalize_event(event)

    def delete_event(self, event_id: str, *, calendar_id: str = "primary") -> dict[str, Any]:
        event_id = event_id.strip()
        if not event_id:
            raise CalendarError("event_id is required")
        service = self._service()
        self._execute(
            service.events().delete(
                calendarId=calendar_id or "primary",
                eventId=event_id,
                sendUpdates="none",
            )
        )
        return {
            "event_id": event_id,
            "deleted": True,
        }

    @staticmethod
    def _event_time(value: str, time_zone: str | None) -> dict[str, str]:
        value = str(value).strip()
        if not value:
            raise CalendarError("event start/end is required")
        if _DATE_RE.fullmatch(value):
            return {"date": value}
        result = {"dateTime": value}
        if time_zone:
            result["timeZone"] = str(time_zone).strip()
        return result

    @staticmethod
    def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
        start = event.get("start") or {}
        end = event.get("end") or {}
        reminders = event.get("reminders") or {}
        return {
            "id": str(event.get("id", "")),
            "summary": str(event.get("summary", "")),
            "description": str(event.get("description", "")),
            "location": str(event.get("location", "")),
            "status": str(event.get("status", "")),
            "start": start.get("dateTime") or start.get("date") or "",
            "end": end.get("dateTime") or end.get("date") or "",
            "time_zone": start.get("timeZone") or end.get("timeZone") or "",
            "html_link": str(event.get("htmlLink", "")),
            "organizer": str((event.get("organizer") or {}).get("email", "")),
            "attendees": [
                str(item.get("email", ""))
                for item in event.get("attendees", []) or []
                if isinstance(item, dict) and item.get("email")
            ],
            "reminders": reminders,
            "untrusted_external_content": True,
        }

    def _credentials(self):
        if not self.token_file.exists():
            raise CalendarNotConnectedError(
                "Calendar has not been authorized yet. Run the local Calendar authorization helper."
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
    def _execute(request):
        try:
            result = request.execute()
            return result if result is not None else {}
        except Exception as exc:
            raise CalendarError(f"Calendar API request failed: {type(exc).__name__}") from exc

    def _save_credentials(self, credentials) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        try:
            os.chmod(self.token_file, 0o600)
        except OSError:
            pass
