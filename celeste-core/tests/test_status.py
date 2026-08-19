from fastapi.testclient import TestClient

from app.main import app


def test_status_is_online(tmp_path, monkeypatch):
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    with TestClient(app) as client:
        response = client.get("/api/v1/status")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Celeste"
    assert body["status"] == "online"
    assert body["version"] == "0.4.0"
    assert body["brain_ready"] is True
