from __future__ import annotations

import base64
import os
import re
from email.message import EmailMessage
from email.utils import parseaddr
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GmailError(ValueError):
    pass


class GmailNotConnectedError(GmailError):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def _decode_base64url(value: str) -> str:
    if not value:
        return ""
    padding = "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise GmailError("Gmail returned invalid base64url message data") from exc
    return raw.decode("utf-8", errors="replace")


def _encode_message(message: EmailMessage) -> str:
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _clean_header(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise GmailError(f"{field} is required")
    if "\r" in value or "\n" in value:
        raise GmailError(f"Invalid newline in {field}")
    return value


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in payload.get("headers", []) or []:
        name = str(item.get("name", "")).strip().lower()
        if name:
            result[name] = str(item.get("value", ""))
    return result


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", value)
    return parser.text()


def _extract_body(payload: dict[str, Any]) -> str:
    mime_type = str(payload.get("mimeType", "")).lower()
    body = payload.get("body") or {}
    data = str(body.get("data", ""))

    if mime_type == "text/plain" and data:
        return _decode_base64url(data)

    parts = payload.get("parts") or []
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_type = str(part.get("mimeType", "")).lower()
        if part_type == "text/plain":
            text = _extract_body(part)
            if text:
                plain_parts.append(text)
        elif part_type == "text/html":
            part_data = str((part.get("body") or {}).get("data", ""))
            if part_data:
                html_parts.append(_html_to_text(_decode_base64url(part_data)))
        elif part.get("parts"):
            nested = _extract_body(part)
            if nested:
                plain_parts.append(nested)

    if plain_parts:
        return "\n\n".join(plain_parts)
    if html_parts:
        return "\n\n".join(html_parts)
    if mime_type == "text/html" and data:
        return _html_to_text(_decode_base64url(data))
    return ""


class GmailClient:
    """Small Gmail API boundary used by Celeste tools.

    OAuth tokens never leave this service. Tool results deliberately mark email
    content as untrusted external data before it can be shown to an AI provider.
    """

    def __init__(self, credentials_file: Path, token_file: Path):
        self.credentials_file = credentials_file
        self.token_file = token_file

    def status(self, enabled: bool) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "credentials_present": self.credentials_file.exists(),
            "authorized": self.token_file.exists(),
            "scopes": list(GMAIL_SCOPES),
        }

    def authorize_interactive(self) -> dict[str, Any]:
        if not self.credentials_file.exists():
            raise GmailNotConnectedError(
                f"Gmail OAuth credentials file not found: {self.credentials_file}"
            )
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise GmailError("Google OAuth dependencies are not installed") from exc

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_file),
            GMAIL_SCOPES,
        )
        credentials = flow.run_local_server(port=0)
        self._save_credentials(credentials)
        return {
            "authorized": True,
            "scopes": list(GMAIL_SCOPES),
        }

    def search_messages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise GmailError("query is required")
        limit = max(1, min(int(limit), 10))
        service = self._service()
        response = self._execute(
            service.users().messages().list(
                userId="me",
                q=query,
                maxResults=limit,
                includeSpamTrash=False,
            )
        )
        results: list[dict[str, Any]] = []
        for item in response.get("messages", []) or []:
            message_id = str(item.get("id", ""))
            if not message_id:
                continue
            message = self._execute(
                service.users().messages().get(
                    userId="me",
                    id=message_id,
                    format="metadata",
                    metadataHeaders=["From", "To", "Cc", "Subject", "Date", "Message-ID"],
                )
            )
            results.append(self._message_metadata(message))
        return results

    def list_unread(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.search_messages("is:unread in:inbox", limit=limit)

    def read_message(self, message_id: str) -> dict[str, Any]:
        message_id = message_id.strip()
        if not message_id:
            raise GmailError("message_id is required")
        service = self._service()
        message = self._execute(
            service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            )
        )
        metadata = self._message_metadata(message)
        body = _extract_body(message.get("payload") or {}).strip()
        truncated = len(body) > 12_000
        metadata.update(
            {
                "body": body[:12_000],
                "body_truncated": truncated,
                "untrusted_external_content": True,
            }
        )
        return metadata

    def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
    ) -> dict[str, Any]:
        to = _clean_header(to, "to")
        subject = _clean_header(subject, "subject")
        if cc is not None:
            cc = _clean_header(cc, "cc")

        message = EmailMessage()
        message["To"] = to
        if cc:
            message["Cc"] = cc
        message["Subject"] = subject
        message.set_content(body)

        service = self._service()
        draft = self._execute(
            service.users().drafts().create(
                userId="me",
                body={"message": {"raw": _encode_message(message)}},
            )
        )
        return {
            "draft_id": str(draft.get("id", "")),
            "message_id": str((draft.get("message") or {}).get("id", "")),
            "thread_id": str((draft.get("message") or {}).get("threadId", "")),
            "to": to,
            "cc": cc,
            "subject": subject,
            "sent": False,
        }

    def create_reply_draft(self, *, message_id: str, body: str) -> dict[str, Any]:
        message_id = message_id.strip()
        if not message_id:
            raise GmailError("message_id is required")

        service = self._service()
        original = self._execute(
            service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            )
        )
        headers = _headers(original.get("payload") or {})
        sender = headers.get("from", "")
        recipient = parseaddr(sender)[1] or sender
        recipient = _clean_header(recipient, "reply recipient")
        original_subject = headers.get("subject", "").strip() or "(sin asunto)"
        subject = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"

        reply = EmailMessage()
        reply["To"] = recipient
        reply["Subject"] = subject
        original_message_id = headers.get("message-id", "").strip()
        references = headers.get("references", "").strip()
        if original_message_id:
            reply["In-Reply-To"] = original_message_id
            reply["References"] = " ".join(
                value for value in (references, original_message_id) if value
            )
        reply.set_content(body)

        draft_body: dict[str, Any] = {
            "message": {
                "raw": _encode_message(reply),
                "threadId": str(original.get("threadId", "")),
            }
        }
        draft = self._execute(
            service.users().drafts().create(userId="me", body=draft_body)
        )
        return {
            "draft_id": str(draft.get("id", "")),
            "message_id": str((draft.get("message") or {}).get("id", "")),
            "thread_id": str((draft.get("message") or {}).get("threadId", "")),
            "to": recipient,
            "subject": subject,
            "reply_to_message_id": message_id,
            "sent": False,
        }

    def draft_metadata(self, draft_id: str) -> dict[str, Any]:
        draft_id = draft_id.strip()
        if not draft_id:
            raise GmailError("draft_id is required")
        service = self._service()
        draft = self._execute(
            service.users().drafts().get(
                userId="me",
                id=draft_id,
                format="metadata",
            )
        )
        message = draft.get("message") or {}
        metadata = self._message_metadata(message)
        metadata["draft_id"] = draft_id
        return metadata

    def send_draft(self, draft_id: str) -> dict[str, Any]:
        draft_id = draft_id.strip()
        if not draft_id:
            raise GmailError("draft_id is required")
        service = self._service()
        sent = self._execute(
            service.users().drafts().send(
                userId="me",
                body={"id": draft_id},
            )
        )
        return {
            "draft_id": draft_id,
            "message_id": str(sent.get("id", "")),
            "thread_id": str(sent.get("threadId", "")),
            "sent": True,
        }

    @staticmethod
    def _message_metadata(message: dict[str, Any]) -> dict[str, Any]:
        headers = _headers(message.get("payload") or {})
        return {
            "id": str(message.get("id", "")),
            "thread_id": str(message.get("threadId", "")),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "message_id_header": headers.get("message-id", ""),
            "snippet": str(message.get("snippet", ""))[:1000],
            "labels": list(message.get("labelIds", []) or []),
            "untrusted_external_content": True,
        }

    def _credentials(self):
        if not self.token_file.exists():
            raise GmailNotConnectedError(
                "Gmail has not been authorized yet. Run the local Gmail authorization helper."
            )
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise GmailError("Google authentication dependencies are not installed") from exc

        try:
            credentials = Credentials.from_authorized_user_file(
                str(self.token_file),
                GMAIL_SCOPES,
            )
        except Exception as exc:
            raise GmailNotConnectedError("Could not read the Gmail OAuth token") from exc

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception as exc:
                raise GmailNotConnectedError("Could not refresh the Gmail OAuth token") from exc
            self._save_credentials(credentials)

        if not credentials.valid:
            raise GmailNotConnectedError(
                "Gmail authorization is invalid or expired. Re-run the authorization helper."
            )
        return credentials

    def _service(self):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GmailError("Google API client dependency is not installed") from exc
        try:
            return build(
                "gmail",
                "v1",
                credentials=self._credentials(),
                cache_discovery=False,
            )
        except GmailError:
            raise
        except Exception as exc:
            raise GmailError(f"Could not initialize Gmail API: {type(exc).__name__}") from exc

    @staticmethod
    def _execute(request):
        try:
            return request.execute()
        except Exception as exc:
            raise GmailError(f"Gmail API request failed: {type(exc).__name__}") from exc

    def _save_credentials(self, credentials) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        try:
            os.chmod(self.token_file, 0o600)
        except OSError:
            pass
