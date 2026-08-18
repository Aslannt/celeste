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
    openai_api_key: str | None
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
        llm_model = os.getenv("CELESTE_LLM_MODEL", "gpt-5").strip() or "gpt-5"
        openai_api_key = os.getenv("OPENAI_API_KEY") or None

        return cls(
            api_token=api_token,
            brain_dir=brain_dir,
            llm_provider=llm_provider,
            llm_model=llm_model,
            openai_api_key=openai_api_key,
        )
