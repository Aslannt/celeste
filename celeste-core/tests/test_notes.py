from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

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
