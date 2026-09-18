from __future__ import annotations

import httpx

from app.config import Settings


class WebSearchError(RuntimeError):
    pass


class SearxngClient:
    """Thin client for a self-hosted SearXNG instance (see docker/searxng/).

    Local and free by design: no API key, no request quota, so Celeste never
    has to ration internet lookups. Results are external content and must be
    treated as untrusted (CLAUDE.md regla dura 3), same as Gmail/Calendar.
    """

    def __init__(self, base_url: str, timeout_seconds: float = 10.0):
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        try:
            response = self.client.get(
                "/search",
                params={"q": query, "format": "json"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise WebSearchError(f"SearXNG request failed: {exc}") from exc

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise WebSearchError("SearXNG returned an unexpected search payload")

        results: list[dict[str, str]] = []
        for item in raw_results[:limit]:
            if not isinstance(item, dict):
                continue
            results.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": str(item.get("url") or ""),
                    "content": str(item.get("content") or ""),
                }
            )
        return results


def build_web_search_client(settings: Settings) -> SearxngClient | None:
    """Opt-in like Gmail/Calendar/embeddings; None means the tool must not be registered."""
    if not settings.web_search_enabled:
        return None
    return SearxngClient(settings.searxng_url)
