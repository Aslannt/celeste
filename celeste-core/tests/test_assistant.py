from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.ai import OpenAIProvider
from app.services.tools import ToolRisk, ToolRouter, ToolSpec

TOKEN = "assistant-test-token"
HEADERS = {"X-Celeste-Token": TOKEN}


def _configure(tmp_path: Path, monkeypatch) -> Path:
    brain = tmp_path / "CelesteBrain"
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(brain))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    return brain


def test_assistant_exposes_permissioned_tools(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/api/v1/assistant/tools", headers=HEADERS)

    assert response.status_code == 200
    tools = {item["name"]: item["risk"] for item in response.json()["tools"]}
    assert tools["search_memory"] == "READ"
    assert tools["create_note"] == "SAFE_WRITE"
    assert tools["update_note"] == "CONFIRM"
    assert tools["delete_note"] == "CONFIRM"
    assert tools["get_pc_status"] == "READ"


def test_local_assistant_searches_brain_through_tool_router(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Mantenimiento de la moto",
                "content": "Cambiar el aceite antes del proximo viaje.",
                "tags": ["moto", "mantenimiento"],
            },
        )
        assert created.status_code == 201

        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={"message": "Busca moto"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local_rules"
    assert "Mantenimiento de la moto" in body["reply"]
    assert body["events"][0]["tool"] == "search_memory"
    assert body["events"][0]["status"] == "executed"


def test_local_assistant_creates_durable_note_and_indexes_it(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={"message": "Recuerda que comprar filtro de aceite para la moto"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["events"][0]["tool"] == "create_note"
        assert body["events"][0]["status"] == "executed"

        search = client.get(
            "/api/v1/notes/search?q=filtro&limit=10",
            headers=HEADERS,
        )

    assert search.status_code == 200
    assert any("filtro de aceite" in note["content"].lower() for note in search.json())
    assert len(list((brain / "notes").glob("*.md"))) == 1


def test_local_assistant_reads_pc_status(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={"message": "Cual es el estado del PC?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["events"][0]["tool"] == "get_pc_status"
    assert body["events"][0]["status"] == "executed"
    assert body["events"][0]["output"]["version"] == "0.4.2"


def test_confirm_tool_never_executes_before_confirmation(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    router = ToolRouter(Settings.from_env())
    calls: list[str] = []
    router.register(
        ToolSpec(
            name="test_sensitive_action",
            description="Test-only confirmation action.",
            risk=ToolRisk.CONFIRM,
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=lambda _: calls.append("executed") or {"ok": True},
        )
    )

    pending = router.execute("test_sensitive_action", {})
    assert pending.status == "confirmation_required"
    assert pending.confirmation_id is not None
    assert calls == []

    confirmed = router.confirm(pending.confirmation_id)
    assert confirmed is not None
    assert confirmed.status == "executed"
    assert calls == ["executed"]


def test_delete_note_requires_confirmation_and_can_be_cancelled(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={"title": "No borrar aun", "content": "contenido privado", "tags": []},
        ).json()

        router = ToolRouter(Settings.from_env())
        pending = router.execute("delete_note", {"note_id": created["id"]})
        assert pending.status == "confirmation_required"
        assert pending.confirmation_id is not None
        assert "No borrar aun" in (pending.summary or "")

        listed = client.get("/api/v1/assistant/confirmations", headers=HEADERS)
        assert listed.status_code == 200
        assert any(item["confirmation_id"] == pending.confirmation_id for item in listed.json())

        cancelled = client.delete(
            f"/api/v1/assistant/confirm/{pending.confirmation_id}",
            headers=HEADERS,
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        still_there = client.get(f"/api/v1/notes/{created['id']}", headers=HEADERS)
        assert still_there.status_code == 200
        assert still_there.json()["deleted"] is False


def test_delete_note_executes_only_after_confirmation(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={"title": "Borrado confirmado", "content": "temporal", "tags": ["confirm"]},
        ).json()

        router = ToolRouter(Settings.from_env())
        pending = router.execute("delete_note", {"note_id": created["id"]})
        confirmed = client.post(
            f"/api/v1/assistant/confirm/{pending.confirmation_id}",
            headers=HEADERS,
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "executed"
        assert confirmed.json()["output"]["deleted"] is True

        note = client.get(f"/api/v1/notes/{created['id']}", headers=HEADERS)
        assert note.status_code == 200
        assert note.json()["deleted"] is True

        search = client.get("/api/v1/notes/search?q=confirm", headers=HEADERS)
        assert search.status_code == 200
        assert all(item["id"] != created["id"] for item in search.json())


def test_tool_audit_does_not_log_tool_arguments_outputs_or_summaries(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)
    secret_text = "super-private-audit-payload-7421"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={"message": f"Recuerda que {secret_text}"},
        )
        assert response.status_code == 200
        audit = client.get("/api/v1/assistant/audit?limit=20", headers=HEADERS)

    assert audit.status_code == 200
    events = audit.json()["events"]
    assert any(item["tool"] == "create_note" for item in events)
    assert all("summary" not in item for item in events)
    raw_audit = (brain / ".celeste" / "tool-audit.jsonl").read_text(encoding="utf-8")
    assert secret_text not in raw_audit


def test_openai_provider_disables_remote_storage_and_parallel_tool_calls(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    calls: list[dict] = []

    class FakeFunctionCall:
        type = "function_call"
        name = "get_pc_status"
        arguments = "{}"
        call_id = "call_test"

    class FakeResponse:
        def __init__(self, output, output_text=""):
            self.output = output
            self.output_text = output_text

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return FakeResponse([FakeFunctionCall()])
            return FakeResponse([], "Core consultado correctamente")

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **_: FakeClient())
    provider = OpenAIProvider("test-key", "gpt-5.6", 30)
    result = provider.answer("Como esta el PC?", ToolRouter(Settings.from_env()))

    assert result.reply == "Core consultado correctamente"
    assert result.events[0].tool == "get_pc_status"
    assert all(call["store"] is False for call in calls)
    assert all(call["parallel_tool_calls"] is False for call in calls)
    assert any(
        isinstance(item, dict) and item.get("type") == "function_call_output"
        for item in calls[1]["input"]
    )


def test_openai_provider_stops_immediately_when_confirmation_is_required(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    api_calls: list[dict] = []
    handler_calls: list[str] = []

    class FakeFunctionCall:
        type = "function_call"
        name = "test_confirm_action"
        arguments = "{}"
        call_id = "call_confirm"

    class FakeResponse:
        output = [FakeFunctionCall()]
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            api_calls.append(kwargs)
            return FakeResponse()

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **_: FakeClient())
    router = ToolRouter(Settings.from_env())
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

    result = OpenAIProvider("test-key", "gpt-5.6", 30).answer("Haz la accion", router)

    assert len(api_calls) == 1
    assert handler_calls == []
    assert result.events[0].status == "confirmation_required"
    assert result.events[0].confirmation_id is not None
    assert "confirmacion" in result.reply.lower()
