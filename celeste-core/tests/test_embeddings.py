from __future__ import annotations

from pathlib import Path

import httpx

from app.config import Settings
from app.services.embeddings import EmbeddingError, OllamaEmbeddingClient, build_embedding_client


def _configure(tmp_path: Path, monkeypatch, **overrides) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", "embeddings-test-token")
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

    def post(self, path: str, json: dict) -> FakeResponse:
        self.calls.append({"path": path, "json": json})
        return self.response


def test_embed_returns_vectors_for_each_text(monkeypatch):
    fake = FakeClient(FakeResponse({"embeddings": [[0.1, 0.2], [0.3, 0.4]]}))
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    client = OllamaEmbeddingClient("http://127.0.0.1:11434", "bge-m3")
    vectors = client.embed(["hola", "mundo"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert fake.calls[0]["path"] == "/api/embed"
    assert fake.calls[0]["json"] == {"model": "bge-m3", "input": ["hola", "mundo"]}


def test_embed_empty_list_makes_no_request(monkeypatch):
    fake = FakeClient(FakeResponse({"embeddings": []}))
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    client = OllamaEmbeddingClient("http://127.0.0.1:11434", "bge-m3")
    assert client.embed([]) == []
    assert fake.calls == []


def test_embed_raises_on_malformed_payload(monkeypatch):
    fake = FakeClient(FakeResponse({"embeddings": [[0.1]]}))  # length mismatch
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    client = OllamaEmbeddingClient("http://127.0.0.1:11434", "bge-m3")
    try:
        client.embed(["uno", "dos"])
    except EmbeddingError:
        pass
    else:
        raise AssertionError("expected EmbeddingError for mismatched payload")


def test_embed_raises_when_client_errors(monkeypatch):
    class BrokenClient:
        def post(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(httpx, "Client", lambda **_: BrokenClient())

    client = OllamaEmbeddingClient("http://127.0.0.1:11434", "bge-m3")
    try:
        client.embed(["hola"])
    except EmbeddingError:
        pass
    else:
        raise AssertionError("expected EmbeddingError when the request fails")


def test_build_embedding_client_disabled_by_default(tmp_path, monkeypatch):
    # Matches CELESTE_GMAIL_ENABLED/CELESTE_CALENDAR_ENABLED: opt-in only,
    # since it requires `ollama pull bge-m3` first and must not surprise
    # existing setups with a new outbound call on every note write.
    settings = _configure(tmp_path, monkeypatch)
    assert build_embedding_client(settings) is None


def test_build_embedding_client_explicitly_disabled_returns_none(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, CELESTE_EMBEDDINGS_ENABLED="false")
    assert build_embedding_client(settings) is None


def test_build_embedding_client_enabled_returns_client(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch, CELESTE_EMBEDDINGS_ENABLED="true")
    client = build_embedding_client(settings)
    assert isinstance(client, OllamaEmbeddingClient)
    assert client.model == "bge-m3"
