from __future__ import annotations

from app.config import Settings
from app.services.gmail import GmailClient, GmailError


def main() -> int:
    settings = Settings.from_env()
    if not settings.gmail_enabled:
        print("[Celeste] Gmail is disabled. Set CELESTE_GMAIL_ENABLED=true in celeste-core/.env first.")
        return 2

    client = GmailClient(
        settings.gmail_credentials_file,
        settings.gmail_token_file,
    )
    state = client.status(enabled=True)
    if not state["credentials_present"]:
        print(
            "[Celeste] Gmail OAuth credentials are missing. Place the Google Desktop app "
            f"credentials at: {settings.gmail_credentials_file}"
        )
        return 2

    print("[Celeste] Opening Google's OAuth authorization flow in your browser...")
    print("[Celeste] Celeste never asks for or stores your Gmail password.")
    try:
        result = client.authorize_interactive()
    except GmailError as exc:
        print(f"[Celeste] Gmail authorization failed: {exc}")
        return 1

    if result.get("authorized"):
        print(f"[Celeste] Gmail authorized. Token saved locally at: {settings.gmail_token_file}")
        return 0

    print("[Celeste] Gmail authorization did not complete.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
