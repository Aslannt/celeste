from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services.llm_tool_scope import message_needs_tool_catalog, scope_router_for_message
from app.services.tools import ToolRouter


def _router(tmp_path: Path, monkeypatch) -> ToolRouter:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", "schedule-test-token")
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    monkeypatch.setenv("CELESTE_GMAIL_ENABLED", "false")
    monkeypatch.setenv("CELESTE_CALENDAR_ENABLED", "true")
    monkeypatch.setenv("CELESTE_CALENDAR_TIME_ZONE", "America/Bogota")
    return ToolRouter(Settings.from_env())


def test_relative_scheduling_language_exposes_tools():
    assert message_needs_tool_catalog("Recuérdame mañana a las 8 comprar leche") is True
    assert message_needs_tool_catalog("¿Qué tengo hoy en el calendario?") is True
    assert message_needs_tool_catalog("Programa una cita mañana") is True


def test_scheduling_tool_schema_includes_current_clock(tmp_path, monkeypatch):
    router = _router(tmp_path, monkeypatch)
    view = scope_router_for_message(router, "Recuérdame mañana a las 8 comprar leche")
    reminder = next(
        schema for schema in view.tool_schemas() if schema["name"] == "create_reminder"
    )

    description = reminder["description"]
    assert "current local date/time is" in description
    assert "America/Bogota" in description
    assert "ISO-8601" in description
    assert "today/tomorrow" in description
