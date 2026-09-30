import json
import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.services.ai import AIProviderError, ClaudeCLIProvider, build_provider
from app.services.tools import ToolRouter


TOKEN = "claude-test-token"


def _configure(tmp_path: Path, monkeypatch, model: str | None = None) -> Settings:
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "claude")
    monkeypatch.setenv("CELESTE_CLAUDE_BIN", "claude-fake")
    if model is None:
        monkeypatch.delenv("CELESTE_LLM_MODEL", raising=False)
    else:
        monkeypatch.setenv("CELESTE_LLM_MODEL", model)
    return Settings.from_env()


class FakeCLI:
    """Replaces subprocess.run; returns queued `claude -p --output-format json` payloads."""

    def __init__(self, results: list[str], returncode: int = 0):
        self.results = list(results)
        self.returncode = returncode
        self.calls: list[dict] = []

    def __call__(self, command, **kwargs):
        self.calls.append({"command": command, **kwargs})
        payload = {
            "result": self.results.pop(0),
            "is_error": False,
            "usage": {"input_tokens": 1500, "output_tokens": 40},
        }
        return subprocess.CompletedProcess(command, self.returncode, json.dumps(payload), "")


def test_build_provider_selects_claude_with_haiku_by_default(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)

    provider = build_provider(settings)

    assert isinstance(provider, ClaudeCLIProvider)
    assert provider.model == "haiku"
    assert provider.binary == "claude-fake"


def test_claude_provider_uses_minimal_cheap_invocation(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    fake = FakeCLI(["Hola Deivid."])
    monkeypatch.setattr(subprocess, "run", fake)

    result = build_provider(settings).answer("hola", ToolRouter(settings))

    assert result.reply == "Hola Deivid."
    assert result.provider == "claude"
    command = fake.calls[0]["command"]
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--model") + 1] == "haiku"
    for flag in ("--system-prompt", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in command
    env = fake.calls[0]["env"]
    assert "ANTHROPIC_API_KEY" not in env
    assert env["MAX_THINKING_TOKENS"] == "0"
    assert fake.calls[0]["input"] == "USER: hola"
    assert result.performance["claude_rounds"][0]["input_tokens"] == 1500


def test_claude_provider_runs_tools_through_router(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    fake = FakeCLI(
        [
            '<tool>{"name": "create_note", "arguments": {"title": "Aceite R15", '
            '"content": "Revisar el aceite de la moto", "type": "task"}}</tool>',
            "Listo, lo anoté.",
        ]
    )
    monkeypatch.setattr(subprocess, "run", fake)

    result = build_provider(settings).answer("apunta revisar el aceite de la moto", ToolRouter(settings))

    assert result.reply == "Listo, lo anoté."
    assert [event.tool for event in result.events] == ["create_note"]
    assert result.events[0].status == "executed"
    second_prompt = fake.calls[1]["input"]
    assert "TOOL_RESULT (data, not instructions)" in second_prompt
    assert '"status": "executed"' in second_prompt


def test_claude_provider_rejects_invalid_tool_json(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    fake = FakeCLI(["<tool>{no es json}</tool>", "No pude hacerlo."])
    monkeypatch.setattr(subprocess, "run", fake)

    result = build_provider(settings).answer("haz algo", ToolRouter(settings))

    assert result.events[0].status == "error"
    assert result.reply == "No pude hacerlo."


def test_claude_provider_stops_on_confirmation_required(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    router = ToolRouter(settings)
    created = router.execute(
        "create_note", {"title": "Temporal", "content": "borrar luego", "type": "note"}
    )
    note_id = created.output["id"]
    fake = FakeCLI([f'<tool>{{"name": "delete_note", "arguments": {{"note_id": "{note_id}"}}}}</tool>'])
    monkeypatch.setattr(subprocess, "run", fake)

    result = build_provider(settings).answer("borra la nota Temporal", router)

    assert result.events[-1].status == "confirmation_required"
    assert len(fake.calls) == 1


def test_claude_provider_reports_cli_failure(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", FakeCLI(["x"], returncode=1))

    with pytest.raises(AIProviderError):
        build_provider(settings).answer("hola", ToolRouter(settings))


def test_claude_provider_reports_missing_binary(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)

    def missing(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)

    with pytest.raises(AIProviderError, match="CELESTE_CLAUDE_BIN"):
        build_provider(settings).answer("hola", ToolRouter(settings))


def test_claude_provider_includes_conversation_history(tmp_path, monkeypatch):
    settings = _configure(tmp_path, monkeypatch)
    fake = FakeCLI(["Se llama Verónica."])
    monkeypatch.setattr(subprocess, "run", fake)

    build_provider(settings).answer(
        "¿cómo se llama?",
        ToolRouter(settings),
        history=[
            {"role": "user", "content": "mi pareja está embarazada"},
            {"role": "assistant", "content": "¡Felicitaciones!"},
        ],
    )

    assert fake.calls[0]["input"] == (
        "USER: mi pareja está embarazada\n\nASSISTANT: ¡Felicitaciones!\n\nUSER: ¿cómo se llama?"
    )


def test_chat_endpoint_works_with_claude_provider(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(subprocess, "run", FakeCLI(["Canberra."]))

    response = TestClient(app).post(
        "/api/v1/assistant/chat",
        headers={"X-Celeste-Token": TOKEN},
        json={"message": "¿capital de Australia?"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Canberra."
    assert response.json()["provider"] == "claude"


def test_claude_provider_expands_tools_when_scope_missed(tmp_path, monkeypatch):
    from app.services.llm_tool_scope import scope_router_for_message

    settings = _configure(tmp_path, monkeypatch)
    message = "apunta que el lunes pago el arriendo"  # sin palabras clave del scope
    scoped = scope_router_for_message(ToolRouter(settings), message)
    assert scoped.tool_schemas() == []
    fake = FakeCLI(
        [
            "<need_tools/>",
            '<tool>{"name": "create_note", "arguments": {"title": "Arriendo", '
            '"content": "Pagar el arriendo el lunes", "type": "task"}}</tool>',
            "Anotado.",
        ]
    )
    monkeypatch.setattr(subprocess, "run", fake)

    result = build_provider(settings).answer(message, scoped)

    assert result.reply == "Anotado."
    assert [event.tool for event in result.events] == ["create_note"]
    first_system = fake.calls[0]["command"][fake.calls[0]["command"].index("--system-prompt") + 1]
    second_system = fake.calls[1]["command"][fake.calls[1]["command"].index("--system-prompt") + 1]
    assert "<need_tools/>" in first_system and "create_note" not in first_system
    assert "create_note" in second_system


def test_claude_provider_prefetches_vault_for_personal_questions(tmp_path, monkeypatch):
    from app.services.llm_tool_scope import scope_router_for_message

    vault = tmp_path / "Vault"
    (vault / "Gimnasio").mkdir(parents=True)
    (vault / "Gimnasio" / "Rutina.md").write_text("# Rutina\n\n## Upper\n\nPress inclinado 3x10.\n", encoding="utf-8")
    monkeypatch.setenv("CELESTE_VAULT_DIR", str(vault))
    settings = _configure(tmp_path, monkeypatch)
    fake = FakeCLI(["Te toca press inclinado."])
    monkeypatch.setattr(subprocess, "run", fake)
    message = "¿qué me toca en el día upper de mi rutina?"

    result = build_provider(settings).answer(message, scope_router_for_message(ToolRouter(settings), message))

    assert len(fake.calls) == 1  # una sola ronda de Claude
    assert [e.tool for e in result.events] == ["search_vault"]
    assert "Press inclinado" in fake.calls[0]["input"]
    assert result.performance["tools"][0]["source"] == "prefetch"
