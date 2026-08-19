from __future__ import annotations

from app.config import Settings
from app.services.calendar import CalendarError, GoogleCalendarClient


def main() -> int:
    settings = Settings.from_env()
    if not settings.calendar_enabled:
        print(
            "[Celeste] Calendar is disabled. Set CELESTE_CALENDAR_ENABLED=true "
            "in celeste-core/.env first."
        )
        return 2

    client = GoogleCalendarClient(
        settings.calendar_credentials_file,
        settings.calendar_token_file,
    )
    state = client.status(enabled=True)
    if not state["credentials_present"]:
        print(
            "[Celeste] Google OAuth Desktop credentials are missing. Calendar reuses the same "
            f"client JSON by default. Expected file: {settings.calendar_credentials_file}"
        )
        return 2

    print("[Celeste] Opening Google's Calendar OAuth authorization flow in your browser...")
    print("[Celeste] Scope requested: calendar.events only. Celeste does not request calendar-wide sharing/admin access.")
    try:
        result = client.authorize_interactive()
    except CalendarError as exc:
        print(f"[Celeste] Calendar authorization failed: {exc}")
        return 1

    if result.get("authorized"):
        print(f"[Celeste] Calendar authorized. Token saved locally at: {settings.calendar_token_file}")
        return 0

    print("[Celeste] Calendar authorization did not complete.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
