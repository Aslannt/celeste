from pathlib import Path

import httpx

from app.config import Settings
from app.services.ai import OllamaProvider, build_provider
from app.services.llm_tool_scope import scope_router_for_message
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
    assert result.performance is not None
    assert result.performance["model"] == "qwen3.5:9b"
    assert result.performance["total_ms"] >= 0
    assert len(result.performance["ollama_rounds"]) == 2
    assert result.performance["tools"][0]["tool"] == "get_pc_status"
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


def test_ollama_search_memory_round_includes_grounding_context(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    calls: list[dict] = []
    router = ToolRouter(settings)
    created = router.execute(
        "create_note",
        {
            "title": "Recordatorio: revisar llantas el sabado",
            "content": "El proximo sabado debo revisar la presion de las llantas.",
            "type": "task",
            "tags": ["recordatorio", "moto"],
        },
    )
    assert created.status == "executed"

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
                                "arguments": {"query": "moto llantas", "limit": 5},
                            }
                        }
                    ],
                }
            },
            {"message": {"role": "assistant", "content": "Respuesta final"}},
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    view = scope_router_for_message(router, "Revisa lo que recuerdas sobre la moto")
    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer("Revisa lo que recuerdas sobre la moto", view)

    assert result.reply == "Respuesta final"
    assert len(calls) == 2
    tool_messages = [
        message
        for message in calls[1]["json"]["messages"]
        if message.get("role") == "tool" and message.get("tool_name") == "search_memory"
    ]
    assert len(tool_messages) == 1
    assert "_celeste_context" in tool_messages[0]["content"]
    assert "not schedules" in tool_messages[0]["content"]
    assert "do not invent technical or domain facts" in tool_messages[0]["content"]


def test_ollama_provider_exposes_server_performance_metrics(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    calls: list[dict] = []
    fake = FakeClient(
        [
            {
                "message": {
                    "role": "assistant",
                    "content": "Respuesta medida",
                },
                "total_duration": 2_000_000_000,
                "load_duration": 100_000_000,
                "prompt_eval_count": 120,
                "prompt_eval_duration": 500_000_000,
                "eval_count": 50,
                "eval_duration": 1_000_000_000,
            }
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer("Responde algo", ToolRouter(settings))

    assert result.performance is not None
    round_metrics = result.performance["ollama_rounds"][0]
    assert round_metrics["server_total_ms"] == 2000.0
    assert round_metrics["load_ms"] == 100.0
    assert round_metrics["prompt_tokens"] == 120
    assert round_metrics["prompt_eval_ms"] == 500.0
    assert round_metrics["generated_tokens"] == 50
    assert round_metrics["generation_ms"] == 1000.0
    assert round_metrics["generation_tokens_per_second"] == 50.0


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
    assert result.performance is not None
    assert result.performance["tools"][0]["tool"] == "create_note"
    assert result.performance["tools"][0]["source"] == "deterministic_fallback"

    output = result.events[0].output
    assert isinstance(output, dict)
    note = router.storage.get(output["id"])
    assert note.deleted is False
    assert note.content == "esta es una nota temporal para probar confirmaciones V04"


def test_ollama_provider_turns_explicit_delete_after_unique_search_into_confirmation(
    tmp_path,
    monkeypatch,
):
    settings = _configure(tmp_path, monkeypatch)
    calls: list[dict] = []
    router = ToolRouter(settings)
    created = router.execute(
        "create_note",
        {
            "title": "Nota Temporal Confirmaciones V04",
            "content": "nota temporal",
            "type": "note",
            "tags": ["V04"],
        },
    )
    assert created.status == "executed"
    note_id = created.output["id"]

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
                                "arguments": {
                                    "query": "Nota Temporal Confirmaciones V04",
                                    "limit": 5,
                                },
                            }
                        }
                    ],
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Encontre la nota. Deseas que la elimine?",
                }
            },
        ],
        calls,
    )
    monkeypatch.setattr(httpx, "Client", lambda **_: fake)

    result = OllamaProvider(
        settings.ollama_url,
        settings.llm_model,
        settings.llm_timeout_seconds,
        settings.ollama_think,
    ).answer("Busca la nota temporal de confirmaciones V04 y eliminala.", router)

    assert len(calls) == 2
    assert [event.tool for event in result.events] == ["search_memory", "delete_note"]
    assert result.events[0].status == "executed"
    assert result.events[1].risk == ToolRisk.CONFIRM
    assert result.events[1].status == "confirmation_required"
    assert result.events[1].confirmation_id is not None
    assert "confirmacion" in result.reply.lower()
    assert result.performance is not None
    assert [item["tool"] for item in result.performance["tools"]] == [
        "search_memory",
        "delete_note",
    ]
    assert router.storage.get(note_id).deleted is False
