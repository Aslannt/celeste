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


@pytest.fixture(autouse=True)
def _disable_web_search_by_default(monkeypatch):
    """Same override=False leak as embeddings above, now that the real .env
    has CELESTE_WEB_SEARCH_ENABLED=true. Tests that want it on set the env
    var themselves."""
    monkeypatch.setenv("CELESTE_WEB_SEARCH_ENABLED", "false")
