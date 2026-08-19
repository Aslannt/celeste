from pathlib import Path

import httpx

from app.config import Settings
from app.services.ai import OllamaProvider
from app.services.llm_tool_scope import scope_router_for_message
from app.services.tools import ToolRouter


TOKEN = "ollama-grounded-early-exit-token"


def _configure(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CELESTE_LLM_MODEL", "qwen3.5:9b")
    monkeypatch.setenv("CELESTE_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("CELESTE_OLLAMA_THINK", "false")
    return Settings.from_env()


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[dict], calls: list[dict]):
        self.responses = list(responses)
        self.calls = calls

    def post(self, path: str, json: dict) -> FakeResponse:
        self.calls.append({"path": path, "json": json})
        return FakeResponse(self.responses.pop(0))


def test_ollama_priority_memory_stops_after_first_successful_search(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    router = ToolRouter(settings)
    for title in (
        "revisar el aceite de la moto",
        "comprar lubricante para la cadena de la moto",
    ):
        created = router.execute(
            "create_note",
            {
                "title": title,
                "content": title,
                "type": "note",
                "tags": ["moto"],
            },
        )
        assert created.status == "executed"

    calls: list[dict] = []
    fake = FakeClient(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "search_memory",
                                "arguments": {"query": "moto", "limit": 5},
                            }
                        }
                    ],
                }
            }
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    message = (
        "No te habia dicho algo sobre la moto? Revisa lo que recuerdas y dime "
        "que crees que deberia hacer primero y por que."
    )
    view = scope_router_for_message(router, message)
    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer(message, view)

    assert len(calls) == 1
    assert len(result.events) == 1
    assert result.events[0].tool == "search_memory"
    assert result.events[0].status == "executed"
    assert "no puedo determinar con certeza" in result.reply.lower()
    assert result.performance is not None
    assert len(result.performance["ollama_rounds"]) == 1
    assert len(result.performance["tools"]) == 1
    assert result.performance["tools"][0]["tool"] == "search_memory"
