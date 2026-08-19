from __future__ import annotations

from app.config import Settings
from app.services.calendar import CalendarClient, CalendarError


def main() -> int:
    settings = Settings.from_env()
    if not settings.calendar_enabled:
        print(
            "[Celeste] Calendar is disabled. Set CELESTE_CALENDAR_ENABLED=true "
            "in celeste-core/.env first."
        )
        return 2

    client = CalendarClient(
        settings.calendar_credentials_file,
        settings.calendar_token_file,
    )
    state = client.status(enabled=True)
    if not state["credentials_present"]:
        print(
            "[Celeste] Calendar OAuth credentials are missing. Place the Google Desktop app "
            f"credentials at: {settings.calendar_credentials_file}"
        )
        return 2

    print("[Celeste] Opening Google's Calendar OAuth authorization flow in your browser...")
    print("[Celeste] Celeste never asks for or stores your Google password.")
    try:
        result = client.authorize_interactive()
    except CalendarError as exc:
        print(f"[Celeste] Calendar authorization failed: {exc}")
        return 1

    if result.get("authorized"):
        print(
            "[Celeste] Calendar authorized. Token saved locally at: "
            f"{settings.calendar_token_file}"
        )
        return 0

    print("[Celeste] Calendar authorization did not complete.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
