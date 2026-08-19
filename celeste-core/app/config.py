from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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
    version: str = "0.4.0"

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
            llm_timeout_seconds = float(os.getenv("CELESTE_LLM_TIMEOUT_SECONDS", "60"))
        except ValueError:
            llm_timeout_seconds = 60.0
        llm_timeout_seconds = max(5.0, min(llm_timeout_seconds, 300.0))
        openai_api_key = os.getenv("OPENAI_API_KEY") or None
        ollama_url = os.getenv("CELESTE_OLLAMA_URL", "http://127.0.0.1:11434").strip().rstrip("/")
        if not ollama_url:
            ollama_url = "http://127.0.0.1:11434"
        ollama_think = os.getenv("CELESTE_OLLAMA_THINK", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        return cls(
            api_token=api_token,
            brain_dir=brain_dir,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_timeout_seconds=llm_timeout_seconds,
            openai_api_key=openai_api_key,
            ollama_url=ollama_url,
            ollama_think=ollama_think,
        )
