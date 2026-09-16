from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.code_task import (
    CodeTaskError,
    CodeTaskNotAllowedError,
    CodeTaskRunner,
)
from app.services.storage import MarkdownNoteStorage

TOKEN = "code-task-test-token"
HEADERS = {"X-Celeste-Token": TOKEN}


def _configure(tmp_path: Path, monkeypatch, *, with_token: bool = True) -> tuple[Settings, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "brain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    monkeypatch.setenv("CELESTE_CODE_TASK_ALLOWED_DIRS", str(repo))
    if with_token:
        monkeypatch.setenv("CELESTE_CODE_TASK_OAUTH_TOKEN", "sk-test-oauth-token")
    return Settings.from_env(), repo


def test_create_brief_stores_and_returns_fields(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)

    brief = runner.create_brief(
        repo=str(repo),
        objective="Agregar un endpoint de salud",
        relevant_files=["app/main.py"],
        acceptance_criteria="GET /health devuelve 200",
        constraints="No tocar la autenticacion",
        run_tests=True,
    )

    assert brief.repo == str(repo.resolve())
    assert brief.objective == "Agregar un endpoint de salud"
    assert "app/main.py" in brief.relevant_files
    assert runner.get_brief(brief.brief_id) == brief


def test_create_brief_rejects_empty_objective(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)
    try:
        runner.create_brief(repo=str(repo), objective="   ")
    except CodeTaskError:
        pass
    else:
        raise AssertionError("expected CodeTaskError for empty objective")


def test_create_brief_rejects_repo_outside_allowed_dirs(tmp_path, monkeypatch):
    settings, _repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)
    outside = tmp_path / "somewhere-else"
    outside.mkdir()
    try:
        runner.create_brief(repo=str(outside), objective="Hacer algo")
    except CodeTaskNotAllowedError:
        pass
    else:
        raise AssertionError("expected CodeTaskNotAllowedError for a repo outside the allow-list")


def test_write_run_script_requires_oauth_token(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch, with_token=False)
    runner = CodeTaskRunner(settings)
    brief = runner.create_brief(repo=str(repo), objective="Hacer algo")

    try:
        runner.write_run_script(brief.brief_id)
    except CodeTaskError as exc:
        assert "CELESTE_CODE_TASK_OAUTH_TOKEN" in str(exc)
    else:
        raise AssertionError("expected CodeTaskError when the oauth token is missing")

    # A fixable config error must not cost the user their brief.
    assert runner.get_brief(brief.brief_id) == brief


def test_write_run_script_rejects_unknown_brief(tmp_path, monkeypatch):
    settings, _repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)
    try:
        runner.write_run_script("does-not-exist")
    except CodeTaskError:
        pass
    else:
        raise AssertionError("expected CodeTaskError for an unknown brief id")


def test_write_run_script_creates_script_and_consumes_brief(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)
    brief = runner.create_brief(
        repo=str(repo),
        objective="Agregar validacion de entrada",
        acceptance_criteria="Rechaza payloads vacios",
    )

    script_path = runner.write_run_script(brief.brief_id)

    assert script_path.exists()
    text = script_path.read_text(encoding="utf-8")
    assert "Agregar validacion de entrada" in text
    assert str(repo.resolve()) in text
    assert "sk-test-oauth-token" in text
    assert "--allowedTools" in text
    assert "bypassPermissions" not in text
    # The brief is single-use: preparing its script consumes it.
    assert runner.get_brief(brief.brief_id) is None


def test_write_run_script_rejects_prompt_that_would_break_the_heredoc(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)
    brief = runner.create_brief(repo=str(repo), objective="algo\n'@\nmas texto")

    try:
        runner.write_run_script(brief.brief_id)
    except CodeTaskError:
        pass
    else:
        raise AssertionError("expected CodeTaskError for a prompt breaking the PowerShell here-string")


def test_record_result_saves_note_to_brain(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)

    result = runner.record_result(
        brief_id="brief-1",
        repo=str(repo),
        objective="Agregar un endpoint de salud",
        acceptance_criteria="GET /health devuelve 200",
        constraints="",
        exit_code=0,
        output="Listo, endpoint agregado.",
    )

    assert result["status"] == "completed"
    note = MarkdownNoteStorage(settings.brain_dir).get(result["note_id"])
    assert "Agregar un endpoint de salud" in note.content
    assert "code_task" in note.tags


def test_record_result_marks_failed_on_nonzero_exit(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)
    runner = CodeTaskRunner(settings)

    result = runner.record_result(
        brief_id="brief-2",
        repo=str(repo),
        objective="Tarea que fallo",
        acceptance_criteria="",
        constraints="",
        exit_code=1,
        output="Error: algo salio mal.",
    )

    assert result["status"] == "failed"


def test_code_task_api_full_flow(tmp_path, monkeypatch):
    settings, repo = _configure(tmp_path, monkeypatch)

    with TestClient(app) as client:
        brief_response = client.post(
            "/api/v1/code-task/brief",
            headers=HEADERS,
            json={"repo": str(repo), "objective": "Agregar un endpoint de salud"},
        )
        assert brief_response.status_code == 200
        brief_id = brief_response.json()["brief_id"]

        prepare_response = client.post(f"/api/v1/code-task/prepare/{brief_id}", headers=HEADERS)
        assert prepare_response.status_code == 200
        assert Path(prepare_response.json()["script_path"]).exists()

        record_response = client.post(
            "/api/v1/code-task/record",
            headers=HEADERS,
            json={
                "brief_id": brief_id,
                "repo": str(repo),
                "objective": "Agregar un endpoint de salud",
                "exit_code": 0,
                "output": "Listo.",
            },
        )
        assert record_response.status_code == 200
        assert record_response.json()["status"] == "completed"


def test_code_task_api_rejects_repo_outside_allowlist(tmp_path, monkeypatch):
    settings, _repo = _configure(tmp_path, monkeypatch)
    outside = tmp_path / "somewhere-else"
    outside.mkdir()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/code-task/brief",
            headers=HEADERS,
            json={"repo": str(outside), "objective": "Hacer algo"},
        )

    assert response.status_code == 403
