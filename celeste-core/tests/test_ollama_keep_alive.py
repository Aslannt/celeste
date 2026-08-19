import httpx

from app.services.ai import OllamaProvider
from app.services.tools import ToolRouter
from app.config import Settings


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"role": "assistant", "content": "ok"}}


class FakeClient:
    def __init__(self, calls: list[dict]):
        self.calls = calls

    def post(self, path: str, json: dict) -> FakeResponse:
        self.calls.append({"path": path, "json": json})
        return FakeResponse()


def _settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", "keep-alive-test")
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CELESTE_LLM_MODEL", "qwen3.5:9b")
    monkeypatch.setenv("CELESTE_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("CELESTE_OLLAMA_THINK", "false")
    return Settings.from_env()


def test_ollama_keep_alive_defaults_to_30_minutes(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    monkeypatch.delenv("CELESTE_OLLAMA_KEEP_ALIVE", raising=False)
    calls: list[dict] = []
    monkeypatch.setattr(httpx, "Client", lambda **_: FakeClient(calls))

    provider = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    )
    provider.answer("Hola", ToolRouter(settings))

    assert provider.keep_alive == "30m"
    assert calls[0]["json"]["keep_alive"] == "30m"


def test_ollama_keep_alive_can_be_overridden(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    monkeypatch.setenv("CELESTE_OLLAMA_KEEP_ALIVE", "10m")
    calls: list[dict] = []
    monkeypatch.setattr(httpx, "Client", lambda **_: FakeClient(calls))

    provider = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    )
    provider.answer("Hola", ToolRouter(settings))

    assert provider.keep_alive == "10m"
    assert calls[0]["json"]["keep_alive"] == "10m"
