from __future__ import annotations

from pathlib import Path

import httpx

from app.config import Settings
from app.services.web_search import SearxngClient, WebSearchError, build_web_search_client


def _configure(tmp_path: Path, monkeypatch, **overrides) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", "web-search-test-token")
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    return Settings.from_env()


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    def get(self, path: str, params: dict) -> FakeResponse:
        self.calls.append({"path": path, "params": params})
        return self.response


def test_search_returns_parsed_results(monkeypatch):
    fake = FakeClient(
        FakeResponse(
            {
                "results": [
                    {"title": "Uno", "url": "https://a.example", "content": "contenido a"},
                    {"title": "Dos", "url": "https://b.example", "content": "contenido b"},
                ]
            }
        )
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    client = SearxngClient("http://127.0.0.1:8890")
    results = client.search("clima bogota", limit=5)

    assert results == [
        {"title": "Uno", "url": "https://a.example", "content": "contenido a"},
        {"title": "Dos", "url": "https://b.example", "content": "contenido b"},
    ]
    assert fake.calls[0]["path"] == "/search"
    assert fake.calls[0]["params"] == {"q": "clima bogota", "format": "json"}


def test_search_respects_limit(monkeypatch):
    fake = FakeClient(
        FakeResponse({"results": [{"title": f"R{i}", "url": "https://x", "content": ""} for i in range(10)]})
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    client = SearxngClient("http://127.0.0.1:8890")
    results = client.search("algo", limit=2)

    assert len(results) == 2


def test_search_raises_on_malformed_payload(monkeypatch):
    fake = FakeClient(FakeResponse({"unexpected": "shape"}))
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    client = SearxngClient("http://127.0.0.1:8890")
    try:
        client.search("algo")
    except WebSearchError:
        pass
    else:
        raise AssertionError("expected WebSearchError for a malformed payload")


def test_search_raises_when_client_errors(monkeypatch):
    class BrokenClient:
        def get(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(httpx, "Client", lambda **_: BrokenClient())

    client = SearxngClient("http://127.0.0.1:8890")
    try:
        client.search("algo")
    except WebSearchError:
        pass
    else:
        raise AssertionError("expected WebSearchError when the request fails")


def test_build_web_search_client_disabled_by_default(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    assert build_web_search_client(settings) is None


def test_build_web_search_client_enabled_returns_client(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, CELESTE_WEB_SEARCH_ENABLED="true")
    client = build_web_search_client(settings)
    assert isinstance(client, SearxngClient)
