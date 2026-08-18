from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_token: str
    brain_dir: Path
    version: str = "0.1.0"

    @classmethod
    def from_env(cls) -> "Settings":
        core_dir = Path(__file__).resolve().parents[1]
        repo_dir = core_dir.parent
        default_brain = repo_dir / "CelesteBrain"
        brain_dir = Path(os.getenv("CELESTE_BRAIN_DIR", str(default_brain))).expanduser()
        api_token = os.getenv("CELESTE_API_TOKEN", "celeste-local-dev")
        return cls(api_token=api_token, brain_dir=brain_dir)
