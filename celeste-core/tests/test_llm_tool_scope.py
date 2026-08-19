from pathlib import Path

from app.config import Settings
from app.services.llm_tool_scope import message_needs_tool_catalog, scope_router_for_message
from app.services.tools import ToolRouter


TOKEN = "tool-scope-test-token"


def _router(tmp_path: Path, monkeypatch) -> ToolRouter:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CELESTE_LLM_MODEL", "qwen3.5:9b")
    return ToolRouter(Settings.from_env())


def test_clear_conversation_omits_tool_schemas(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    view = scope_router_for_message(
        router,
        "Explicame en una sola frase que puedes hacer por mi.",
    )

    assert message_needs_tool_catalog("Explicame en una sola frase que puedes hacer por mi.") is False
    assert view.tool_schemas() == []


def test_personal_memory_cues_keep_full_tool_catalog(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    expected_names = {schema["name"] for schema in router.tool_schemas()}

    messages = [
        "No te habia dicho que tenia algo pendiente con la moto?",
        "Puedes revisar mis notas sobre la moto?",
        "Quiero modificar una nota anterior.",
        "Que recuerdas de lo que hablamos la ultima vez?",
    ]

    for message in messages:
        view = scope_router_for_message(router, message)
        assert message_needs_tool_catalog(message) is True
        assert {schema["name"] for schema in view.tool_schemas()} == expected_names


def test_schema_view_still_delegates_real_tool_execution(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    view = scope_router_for_message(router, "Cual es el estado del PC?")

    event = view.execute("get_pc_status", {})

    assert event.tool == "get_pc_status"
    assert event.status == "executed"
