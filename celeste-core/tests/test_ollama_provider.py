from pathlib import Path

import httpx

from app.config import Settings
from app.services.ai import OllamaProvider, build_provider
from app.services.tools import ToolRisk, ToolRouter, ToolSpec


TOKEN = "ollama-test-token"


def _configure(tmp_path: Path, monkeypatch) -> Settings:
    brain = tmp_path / "CelesteBrain"
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(brain))
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


def test_build_provider_selects_ollama_from_settings(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(httpx, "Client", lambda **_: FakeClient([], []))

    provider = build_provider(settings)

    assert isinstance(provider, OllamaProvider)
    assert provider.model == "qwen3.5:9b"
    assert provider.base_url == "http://127.0.0.1:11434"
    assert provider.think is False


def test_ollama_provider_calls_tools_and_returns_final_answer(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    calls: list[dict] = []
    responses = [
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_pc_status",
                            "arguments": {},
                        }
                    }
                ],
            }
        },
        {
            "message": {
                "role": "assistant",
                "content": "Core consultado localmente",
            }
        },
    ]
    fake = FakeClient(responses, calls)
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer("Como esta el PC?", ToolRouter(settings))

    assert result.provider == "ollama"
    assert result.reply == "Core consultado localmente"
    assert result.events[0].tool == "get_pc_status"
    assert result.events[0].status == "executed"
    assert len(calls) == 2
    assert all(call["path"] == "/api/chat" for call in calls)
    assert all(call["json"]["stream"] is False for call in calls)
    assert all(call["json"]["think"] is False for call in calls)
    assert calls[0]["json"]["model"] == "qwen3.5:9b"
    assert calls[0]["json"]["tools"][0]["type"] == "function"
    assert "function" in calls[0]["json"]["tools"][0]
    assert any(
        message.get("role") == "tool" and message.get("tool_name") == "get_pc_status"
        for message in calls[1]["json"]["messages"]
    )


def test_ollama_provider_stops_before_confirm_tool_executes(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    calls: list[dict] = []
    handler_calls: list[str] = []
    fake = FakeClient(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "test_confirm_action",
                                "arguments": {},
                            }
                        }
                    ],
                }
            }
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    router = ToolRouter(settings)
    router.register(
        ToolSpec(
            name="test_confirm_action",
            description="Sensitive test action.",
            risk=ToolRisk.CONFIRM,
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=lambda _: handler_calls.append("executed") or {"ok": True},
            confirmation_summary=lambda _: "Execute the sensitive test action.",
        )
    )

    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer("Haz la accion", router)

    assert len(calls) == 1
    assert handler_calls == []
    assert result.events[0].status == "confirmation_required"
    assert result.events[0].confirmation_id is not None
    assert "confirmacion" in result.reply.lower()


def test_ollama_provider_falls_back_to_real_note_write_when_model_skips_tool(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    calls: list[dict] = []
    fake = FakeClient(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "He creado la nota en mi memoria.",
                }
            }
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    router = ToolRouter(settings)
    message = "Recuerda que esta es una nota temporal para probar confirmaciones V04"
    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer(message, router)

    assert len(calls) == 1
    assert result.provider == "ollama"
    assert result.events[0].tool == "create_note"
    assert result.events[0].risk == ToolRisk.SAFE_WRITE
    assert result.events[0].status == "executed"
    assert "Celeste Brain" in result.reply

    output = result.events[0].output
    assert isinstance(output, dict)
    note = router.storage.get(output["id"])
    assert note.deleted is False
    assert note.content == "esta es una nota temporal para probar confirmaciones V04"
