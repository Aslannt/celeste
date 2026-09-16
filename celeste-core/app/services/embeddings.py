from __future__ import annotations

import httpx

from app.config import Settings


class EmbeddingError(RuntimeError):
    pass


class OllamaEmbeddingClient:
    """Thin client for Ollama's local embeddings endpoint (/api/embed).

    Mirrors OllamaProvider's httpx usage in app/services/ai.py. Embeddings only
    rank existing FTS5 candidates semantically (see BrainIndex); a failure here
    must never break search_memory, only fall it back to keyword-only search.
    """

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 5.0):
        self.model = model
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self.client.post(
                "/api/embed",
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise EmbeddingError(f"Ollama embedding request failed: {exc}") from exc

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise EmbeddingError("Ollama returned an unexpected embeddings payload")
        return embeddings


def build_embedding_client(settings: Settings) -> OllamaEmbeddingClient | None:
    """Local, free embeddings are independent of the chat provider (openai/local_rules
    can still be configured for chat while search_memory gets semantic ranking).
    Returns None only when explicitly disabled; callers must tolerate that."""
    if not settings.embeddings_enabled:
        return None
    return OllamaEmbeddingClient(settings.ollama_url, settings.embedding_model)
