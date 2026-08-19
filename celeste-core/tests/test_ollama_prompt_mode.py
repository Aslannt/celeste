from pathlib import Path

import httpx

from app.config import Settings
from app.services.ai import (
    OllamaProvider,
    _CELESTE_CONVERSATION_INSTRUCTIONS,
    _CELESTE_INSTRUCTIONS,
)
from app.services.llm_tool_scope import scope_router_for_message
from app.services.tools import ToolRouter


TOKEN = "prompt-mode-test-token"


def _settings(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CELESTE_LLM_MODEL", "qwen3.5:9b")
    monkeypatch.setenv("CELESTE_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("CELESTE_OLLAMA_THINK", "false")
    return Settings.from_env()


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "message": {
                "role": "assistant",
                "content": "Respuesta de prueba",
            }
        }


class FakeClient:
    def __init__(self, calls: list[dict]):
        self.calls = calls

    def post(self, path: str, json: dict) -> FakeResponse:
        self.calls.append({"path": path, "json": json})
        return FakeResponse()


def _provider(settings: Settings, monkeypatch, calls: list[dict]) -> OllamaProvider:
    monkeypatch.setattr(httpx, "Client", lambda **_: FakeClient(calls))
    return OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    )


def test_tool_free_conversation_uses_compact_system_prompt_and_short_budget(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    calls: list[dict] = []
    router = ToolRouter(settings)
    message = "Explicame en dos frases la diferencia entre memoria RAM y almacenamiento."
    view = scope_router_for_message(router, message)

    result = _provider(settings, monkeypatch, calls).answer(message, view)

    assert result.reply == "Respuesta de prueba"
    assert len(calls) == 1
    assert calls[0]["json"]["tools"] == []
    assert calls[0]["json"]["options"] == {"num_predict": 72}
    assert result.performance is not None
    assert result.performance["ollama_rounds"][0]["num_predict_limit"] == 72
    system_prompt = calls[0]["json"]["messages"][0]["content"]
    assert system_prompt == _CELESTE_CONVERSATION_INSTRUCTIONS
    assert len(system_prompt) < len(_CELESTE_INSTRUCTIONS)
    assert "No tools are available" in system_prompt
    assert "keep each sentence short" in system_prompt


def test_generic_tool_free_conversation_is_not_hard_capped(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    calls: list[dict] = []
    router = ToolRouter(settings)
    message = "Explicame con detalle como funciona una base de datos relacional."
    view = scope_router_for_message(router, message)

    result = _provider(settings, monkeypatch, calls).answer(message, view)

    assert result.reply == "Respuesta de prueba"
    assert len(calls) == 1
    assert calls[0]["json"]["tools"] == []
    assert "options" not in calls[0]["json"]
    assert result.performance is not None
    assert "num_predict_limit" not in result.performance["ollama_rounds"][0]


def test_personal_memory_request_keeps_full_system_prompt_and_tools_without_budget(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    calls: list[dict] = []
    router = ToolRouter(settings)
    view = scope_router_for_message(router, "Consulta tu memoria sobre la moto.")

    result = _provider(settings, monkeypatch, calls).answer(
        "Consulta tu memoria sobre la moto.",
        view,
    )

    assert result.reply == "Respuesta de prueba"
    assert len(calls) == 1
    assert calls[0]["json"]["tools"]
    assert "options" not in calls[0]["json"]
    system_prompt = calls[0]["json"]["messages"][0]["content"]
    assert system_prompt == _CELESTE_INSTRUCTIONS
