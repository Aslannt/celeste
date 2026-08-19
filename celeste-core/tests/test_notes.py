from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import NoteCreate
from app.services.storage import MarkdownNoteStorage

TOKEN = "test-token"
HEADERS = {"X-Celeste-Token": TOKEN}


def _configure(tmp_path: Path, monkeypatch) -> Path:
    brain = tmp_path / "CelesteBrain"
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(brain))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    return brain


def test_notes_require_token(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/api/v1/notes")
    assert response.status_code == 401


def test_create_read_update_and_soft_delete_note(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Primera nota de Celeste",
                "content": "Wake-on-LAN funciona.",
                "tags": ["celeste", "wol", "celeste"],
            },
        )
        assert created.status_code == 201
        note = created.json()
        note_id = note["id"]
        assert note["tags"] == ["celeste", "wol"]

        note_files = list((brain / "notes").glob("*.md"))
        assert len(note_files) == 1
        assert "Wake-on-LAN funciona." in note_files[0].read_text(encoding="utf-8")

        fetched = client.get(f"/api/v1/notes/{note_id}", headers=HEADERS)
        assert fetched.status_code == 200
        assert fetched.json()["title"] == "Primera nota de Celeste"

        updated = client.put(
            f"/api/v1/notes/{note_id}",
            headers=HEADERS,
            json={"content": "Wake-on-LAN funciona desde apagado completo."},
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        deleted = client.delete(f"/api/v1/notes/{note_id}", headers=HEADERS)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        visible = client.get("/api/v1/notes", headers=HEADERS)
        assert visible.status_code == 200
        assert visible.json() == []

        all_notes = client.get("/api/v1/notes?include_deleted=true", headers=HEADERS)
        assert len(all_notes.json()) == 1
        assert all_notes.json()[0]["deleted"] is True


def test_create_note_is_idempotent_for_same_key_and_payload(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)
    headers = {**HEADERS, "X-Celeste-Idempotency-Key": "android-local-123"}
    payload = {
        "title": "Nota offline",
        "content": "Se sincroniza una sola vez.",
        "tags": ["android"],
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/notes", headers=headers, json=payload)
        second = client.post("/api/v1/notes", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["idempotency_key"] == "android-local-123"

    note_files = list((brain / "notes").glob("*.md"))
    assert len(note_files) == 1
    assert "idempotency_key: android-local-123" in note_files[0].read_text(encoding="utf-8")


def test_reused_idempotency_key_with_different_payload_returns_conflict(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)
    headers = {**HEADERS, "X-Celeste-Idempotency-Key": "android-local-456"}

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/notes",
            headers=headers,
            json={"title": "Original", "content": "Contenido A"},
        )
        conflict = client.post(
            "/api/v1/notes",
            headers=headers,
            json={"title": "Distinta", "content": "Contenido B"},
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert len(list((brain / "notes").glob("*.md"))) == 1


def test_search_finds_title_content_and_tags(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Mantenimiento de la moto",
                "content": "Cambiar aceite el sabado.",
                "tags": ["vehiculo", "moto"],
            },
        )
        client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Cita prenatal",
                "content": "Control medico el viernes.",
                "tags": ["familia"],
            },
        )

        by_title = client.get("/api/v1/notes/search?q=moto", headers=HEADERS)
        by_content = client.get("/api/v1/notes/search?q=aceite", headers=HEADERS)
        by_tag = client.get("/api/v1/notes/search?q=familia", headers=HEADERS)

    assert by_title.status_code == 200
    assert [note["title"] for note in by_title.json()] == ["Mantenimiento de la moto"]
    assert [note["title"] for note in by_content.json()] == ["Mantenimiento de la moto"]
    assert [note["title"] for note in by_tag.json()] == ["Cita prenatal"]
    assert (brain / ".celeste" / "brain-index.sqlite3").exists()


def test_search_keeps_strict_matches_precise(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Aceite de la moto",
                "content": "Revisar nivel de aceite.",
                "tags": ["moto"],
            },
        )
        client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Casco de la moto",
                "content": "Revisar la visera.",
                "tags": ["moto"],
            },
        )

        response = client.get("/api/v1/notes/search?q=moto%20aceite", headers=HEADERS)

    assert response.status_code == 200
    assert [note["title"] for note in response.json()] == ["Aceite de la moto"]


def test_search_relaxes_natural_language_when_strict_match_is_empty(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Revisar aceite de la moto",
                "content": "Tengo que revisar el aceite de la moto.",
                "tags": ["moto", "mantenimiento"],
            },
        )
        client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={
                "title": "Comprar cafe",
                "content": "Comprar cafe para la cocina.",
                "tags": ["compras"],
            },
        )

        response = client.get(
            "/api/v1/notes/search?q=algo%20pendiente%20con%20la%20moto",
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert [note["title"] for note in response.json()] == ["Revisar aceite de la moto"]


def test_search_index_tracks_update_and_delete(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/notes",
            headers=HEADERS,
            json={"title": "Compra", "content": "Comprar cafe"},
        ).json()
        note_id = created["id"]

        assert len(client.get("/api/v1/notes/search?q=cafe", headers=HEADERS).json()) == 1

        client.put(
            f"/api/v1/notes/{note_id}",
            headers=HEADERS,
            json={"content": "Comprar chocolate"},
        )
        assert client.get("/api/v1/notes/search?q=cafe", headers=HEADERS).json() == []
        assert len(client.get("/api/v1/notes/search?q=chocolate", headers=HEADERS).json()) == 1

        client.delete(f"/api/v1/notes/{note_id}", headers=HEADERS)
        assert client.get("/api/v1/notes/search?q=chocolate", headers=HEADERS).json() == []


def test_rebuild_recovers_markdown_created_outside_api(tmp_path, monkeypatch):
    brain = _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        storage = MarkdownNoteStorage(brain)
        storage.create(
            NoteCreate(
                title="Nota editada fuera del API",
                content="La palabra reconstruible solo existe en Markdown.",
                tags=["manual"],
            )
        )

        before = client.get("/api/v1/notes/search?q=reconstruible", headers=HEADERS)
        rebuilt = client.post("/api/v1/notes/index/rebuild", headers=HEADERS)
        after = client.get("/api/v1/notes/search?q=reconstruible", headers=HEADERS)

    assert before.status_code == 200
    assert before.json() == []
    assert rebuilt.status_code == 200
    assert rebuilt.json() == {"indexed": 1}
    assert [note["title"] for note in after.json()] == ["Nota editada fuera del API"]
