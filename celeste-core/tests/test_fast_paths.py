from pathlib import Path

from fastapi.testclient import TestClient

import app.api.assistant as assistant_api
from app.config import Settings
from app.main import app
from app.services.fast_paths import try_ollama_fast_path
from app.services.tools import ToolRouter


TOKEN = "fast-path-test-token"
HEADERS = {"X-Celeste-Token": TOKEN}


def _configure(tmp_path: Path, monkeypatch) -> Path:
    brain = tmp_path / "CelesteBrain"
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(brain))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CELESTE_LLM_MODEL", "qwen3.5:9b")
    monkeypatch.setenv("CELESTE_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("CELESTE_OLLAMA_THINK", "false")
    return brain


def _forbid_model_build(_settings):
    raise AssertionError("The Ollama provider must not be built for a core fast path")


def test_explicit_remember_skips_ollama_and_writes_real_note(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(assistant_api, "build_provider", _forbid_model_build)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={"message": "Recuerda que comprar filtro de aceite para la moto"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "core_fast_path"
    assert body["events"][0]["tool"] == "create_note"
    assert body["events"][0]["status"] == "executed"
    assert body["performance"]["model_used"] is False
    assert body["performance"]["fast_path"] == "create_note"
    assert body["performance"]["ollama_rounds"] == []
    assert body["performance"]["tools"][0]["source"] == "core_fast_path"
    assert len(list((brain / "notes").glob("*.md"))) == 1


def test_explicit_pc_status_skips_ollama(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(assistant_api, "build_provider", _forbid_model_build)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={"message": "Cual es el estado del PC?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "core_fast_path"
    assert body["events"][0]["tool"] == "get_pc_status"
    assert body["events"][0]["status"] == "executed"
    assert body["performance"]["model_used"] is False
    assert body["performance"]["fast_path"] == "get_pc_status"
    assert body["performance"]["ollama_rounds"] == []


def test_explicit_memory_search_skips_ollama_and_returns_brain_results(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(assistant_api, "build_provider", _forbid_model_build)

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
            json={"message": "¿Que recuerdas sobre la moto? Busca en mi memoria."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "core_fast_path"
    assert body["events"][0]["tool"] == "search_memory"
    assert body["events"][0]["status"] == "executed"
    assert "Mantenimiento de la moto" in body["reply"]
    assert body["performance"]["model_used"] is False
    assert body["performance"]["fast_path"] == "search_memory"
    assert body["performance"]["ollama_rounds"] == []


def test_natural_recall_question_skips_ollama_and_returns_brain_results(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(assistant_api, "build_provider", _forbid_model_build)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Revisar aceite de la moto",
                "content": "Tengo que revisar el aceite de la moto.",
                "tags": ["moto"],
            },
        )
        assert created.status_code == 201

        response = client.post(
            "/api/v1/assistant/chat",
            headers=HEADERS,
            json={
                "message": (
                    "¿No te había dicho que tenía algo pendiente con la moto? "
                    "Revisa si recuerdas algo."
                )
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "core_fast_path"
    assert body["events"][0]["tool"] == "search_memory"
    assert body["events"][0]["status"] == "executed"
    assert "Revisar aceite de la moto" in body["reply"]
    assert body["performance"]["model_used"] is False
    assert body["performance"]["fast_path"] == "search_memory"
    assert body["performance"]["ollama_rounds"] == []


def test_search_fast_path_refuses_mutating_request(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    settings = Settings.from_env()
    router = ToolRouter(settings)

    result = try_ollama_fast_path(
        "Busca la nota temporal de confirmaciones V04 y eliminala.",
        router,
        settings,
    )

    assert result is None


def test_natural_recall_fast_path_refuses_mutating_request(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    settings = Settings.from_env()
    router = ToolRouter(settings)

    result = try_ollama_fast_path(
        (
            "¿No te había dicho que quería eliminar la nota de la moto? "
            "Revisa si recuerdas algo."
        ),
        router,
        settings,
    )

    assert result is None


def test_natural_recall_fast_path_does_not_capture_analysis_request(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    settings = Settings.from_env()
    router = ToolRouter(settings)

    result = try_ollama_fast_path(
        "Revisa mis notas de la moto y dime cual parece mas urgente.",
        router,
        settings,
    )

    assert result is None
