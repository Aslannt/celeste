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


def test_technical_memory_questions_do_not_expose_personal_tools(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    messages = [
        "Explicame en dos frases cual es la diferencia entre memoria RAM y almacenamiento.",
        "Que diferencia hay entre memoria RAM y memoria ROM?",
        "Como funciona la memoria cache de un procesador?",
    ]

    for message in messages:
        view = scope_router_for_message(router, message)
        assert message_needs_tool_catalog(message) is False
        assert view.tool_schemas() == []


def test_personal_memory_cues_keep_full_tool_catalog(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    expected_names = {schema["name"] for schema in router.tool_schemas()}

    messages = [
        "No te habia dicho que tenia algo pendiente con la moto?",
        "Puedes revisar mis notas sobre la moto?",
        "Quiero modificar una nota anterior.",
        "Que recuerdas de lo que hablamos la ultima vez?",
        "Consulta tu memoria sobre la moto.",
        "Que tienes en tu memoria sobre el mantenimiento?",
    ]

    for message in messages:
        view = scope_router_for_message(router, message)
        assert message_needs_tool_catalog(message) is True
        assert {schema["name"] for schema in view.tool_schemas()} == expected_names


def test_search_memory_schema_does_not_present_notes_as_schedules(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    view = scope_router_for_message(router, "Consulta tu memoria sobre la moto.")

    scoped_search = next(
        schema for schema in view.tool_schemas() if schema["name"] == "search_memory"
    )
    original_search = next(
        schema for schema in router.tool_schemas() if schema["name"] == "search_memory"
    )

    description = scoped_search["description"]
    assert "stored notes/tasks, not schedules" in description
    assert "scheduling tool is available" in description
    assert "stored notes/tasks, not schedules" not in original_search["description"]


def test_schema_view_still_delegates_real_tool_execution(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    view = scope_router_for_message(router, "Cual es el estado del PC?")

    event = view.execute("get_pc_status", {})

    assert event.tool == "get_pc_status"
    assert event.status == "executed"
