from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

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
    assert body["events"][0]["output"]["version"] == "0.4.0"
