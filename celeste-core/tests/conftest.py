from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_embeddings_by_default(monkeypatch):
    """Semantic memory calls a real local Ollama endpoint. Settings.from_env()
    loads celeste-core/.env with override=False, so any test whose
    _configure() doesn't mention CELESTE_EMBEDDINGS_ENABLED would silently
    pick up whatever is in the developer's real .env instead of a
    deterministic value - exactly what broke keyword-search assertions once
    the real .env had CELESTE_EMBEDDINGS_ENABLED=true. Tests that want
    embeddings on set the env var themselves inside the test body, which
    simply overrides this default.
    """
    monkeypatch.setenv("CELESTE_EMBEDDINGS_ENABLED", "false")
