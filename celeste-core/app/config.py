from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_token: str
    brain_dir: Path
    llm_provider: str
    llm_model: str
    llm_timeout_seconds: float
    openai_api_key: str | None
    ollama_url: str
    ollama_think: bool
    gmail_enabled: bool
    gmail_credentials_file: Path
    gmail_token_file: Path
    gmail_poll_seconds: int
    calendar_enabled: bool
    calendar_credentials_file: Path
    calendar_token_file: Path
    reminder_poll_seconds: int
    version: str = "0.4.2"

    @classmethod
    def from_env(cls) -> "Settings":
        core_dir = Path(__file__).resolve().parents[1]
        repo_dir = core_dir.parent

        # Local secrets/configuration live in celeste-core/.env and are never
        # committed. Explicit process environment variables still take priority.
        load_dotenv(core_dir / ".env", override=False)

        default_brain = repo_dir / "CelesteBrain"
        brain_dir = Path(os.getenv("CELESTE_BRAIN_DIR", str(default_brain))).expanduser()
        api_token = os.getenv("CELESTE_API_TOKEN", "celeste-local-dev")
        llm_provider = os.getenv("CELESTE_LLM_PROVIDER", "local_rules").strip().lower()

        default_model = "qwen3.5:9b" if llm_provider == "ollama" else "gpt-5.6"
        llm_model = os.getenv("CELESTE_LLM_MODEL", default_model).strip() or default_model

        try:
            llm_timeout_seconds = float(
                os.getenv("CELESTE_LLM_TIMEOUT_SECONDS", "60")
            )
        except ValueError:
            llm_timeout_seconds = 60.0
        llm_timeout_seconds = max(5.0, min(llm_timeout_seconds, 300.0))

        openai_api_key = os.getenv("OPENAI_API_KEY") or None

        ollama_url = (
            os.getenv("CELESTE_OLLAMA_URL", "http://127.0.0.1:11434")
            .strip()
            .rstrip("/")
        )
        if not ollama_url:
            ollama_url = "http://127.0.0.1:11434"

        ollama_think = _env_bool("CELESTE_OLLAMA_THINK", False)

        secrets_dir = core_dir / ".secrets"
        gmail_enabled = _env_bool("CELESTE_GMAIL_ENABLED", False)

        gmail_credentials_file = Path(
            os.getenv(
                "CELESTE_GMAIL_CREDENTIALS_FILE",
                str(secrets_dir / "gmail-credentials.json"),
            )
        ).expanduser()

        gmail_token_file = Path(
            os.getenv(
                "CELESTE_GMAIL_TOKEN_FILE",
                str(secrets_dir / "gmail-token.json"),
            )
        ).expanduser()

        try:
            requested_poll_seconds = int(
                os.getenv("CELESTE_GMAIL_POLL_SECONDS", "0")
            )
        except ValueError:
            requested_poll_seconds = 0

        gmail_poll_seconds = (
            0
            if requested_poll_seconds <= 0
            else max(60, min(requested_poll_seconds, 3600))
        )

        # Calendar reuses the same Desktop OAuth client credentials by default,
        # but has its own token because its least-privilege scope differs from Gmail.
        calendar_enabled = _env_bool("CELESTE_CALENDAR_ENABLED", False)
        calendar_credentials_file = Path(
            os.getenv(
                "CELESTE_CALENDAR_CREDENTIALS_FILE",
                str(gmail_credentials_file),
            )
        ).expanduser()
        calendar_token_file = Path(
            os.getenv(
                "CELESTE_CALENDAR_TOKEN_FILE",
                str(secrets_dir / "calendar-token.json"),
            )
        ).expanduser()

        try:
            requested_reminder_poll = int(
                os.getenv("CELESTE_REMINDER_POLL_SECONDS", "2")
            )
        except ValueError:
            requested_reminder_poll = 2
        reminder_poll_seconds = max(1, min(requested_reminder_poll, 60))

        return cls(
            api_token=api_token,
            brain_dir=brain_dir,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_timeout_seconds=llm_timeout_seconds,
            openai_api_key=openai_api_key,
            ollama_url=ollama_url,
            ollama_think=ollama_think,
            gmail_enabled=gmail_enabled,
            gmail_credentials_file=gmail_credentials_file,
            gmail_token_file=gmail_token_file,
            gmail_poll_seconds=gmail_poll_seconds,
            calendar_enabled=calendar_enabled,
            calendar_credentials_file=calendar_credentials_file,
            calendar_token_file=calendar_token_file,
            reminder_poll_seconds=reminder_poll_seconds,
        )
