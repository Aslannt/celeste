from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.models import NoteCreate
from app.services.embeddings import build_embedding_client
from app.services.index import BrainIndex
from app.services.storage import MarkdownNoteStorage

_BRIEF_TTL_SECONDS = 900.0

# Deliberately scoped, not a permission bypass: the container has network
# access (needed for real tasks - installing deps, etc.), and Anthropic's own
# guidance is that skipping all permission checks is only appropriate for
# sandboxes with NO network access. With network on, an unscoped Bash tool
# could exfiltrate whatever it can read, including its own
# CLAUDE_CODE_OAUTH_TOKEN. This list covers editing files and this project's
# own test/inspection commands; nothing that reaches outside /workspace.
_ALLOWED_TOOLS = "Edit Write Read Glob Grep Bash(python -m pytest*) Bash(pip install*) Bash(git status*) Bash(git diff*)"


class CodeTaskError(ValueError):
    pass


class CodeTaskNotAllowedError(CodeTaskError):
    pass


@dataclass(frozen=True)
class CodeTaskBrief:
    """Fixed-shape brief (design doc section 3.5): what, where, done-when, and
    what not to touch - the fields that actually bound how much an agent
    explores, which is what burns tokens, not the prompt itself."""

    brief_id: str
    repo: str
    objective: str
    relevant_files: list[str]
    acceptance_criteria: str
    constraints: str
    run_tests: bool
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "repo": self.repo,
            "objective": self.objective,
            "relevant_files": self.relevant_files,
            "acceptance_criteria": self.acceptance_criteria,
            "constraints": self.constraints,
            "run_tests": self.run_tests,
        }

    def to_prompt(self) -> str:
        lines = [f"Objetivo: {self.objective}"]
        if self.relevant_files:
            lines.append(
                "Archivos relevantes (prioriza mirar estos antes de explorar el resto):\n"
                + "\n".join(f"- {path}" for path in self.relevant_files)
            )
        if self.acceptance_criteria:
            lines.append(f"Criterio de aceptacion (cuando terminaste): {self.acceptance_criteria}")
        if self.constraints:
            lines.append(f"Restricciones (que NO tocar/hacer): {self.constraints}")
        if self.run_tests:
            lines.append(
                "Corre la suite de tests del proyecto antes de terminar y reporta si quedo en verde."
            )
        return "\n\n".join(lines)


class _BriefStore:
    """Short-lived holding area between "create a brief" and "prepare its
    run script". Mirrors the ConfirmationStore pattern in tools.py, kept
    separate on purpose: code_task is not a Tool Router tool and must not
    share state or a code path with anything the conversational LLM can
    reach.
    """

    def __init__(self, ttl_seconds: float = _BRIEF_TTL_SECONDS):
        self._briefs: dict[str, CodeTaskBrief] = {}
        self._lock = threading.Lock()
        self.ttl_seconds = ttl_seconds

    def put(self, brief: CodeTaskBrief) -> None:
        with self._lock:
            self._expire()
            self._briefs[brief.brief_id] = brief

    def get(self, brief_id: str) -> CodeTaskBrief | None:
        with self._lock:
            self._expire()
            return self._briefs.get(brief_id)

    def pop(self, brief_id: str) -> CodeTaskBrief | None:
        with self._lock:
            self._expire()
            return self._briefs.pop(brief_id, None)

    def _expire(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        expired = [key for key, brief in self._briefs.items() if brief.created_at < cutoff]
        for key in expired:
            del self._briefs[key]


_BRIEFS = _BriefStore()


def _quote_powershell_single(value: str) -> str:
    """Escape a value for a PowerShell single-quoted string ('' is a literal ')."""
    return value.replace("'", "''")


class CodeTaskRunner:
    """Prepares a code_task brief and a ready-to-run sandboxed script for it.

    Deliberately does NOT invoke Docker/Claude Code itself: spawning an
    autonomous coding agent is the single highest-stakes action in this
    project. Keeping a human running that specific command applies ADR-005's
    own principle ("the LLM never touches the system directly") one level up,
    to Celeste's own automation rather than only the conversational LLM. It
    is also not registered in the Tool Router, so the conversational LLM can
    never reach even the brief-preparation step.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def create_brief(
        self,
        *,
        repo: str,
        objective: str,
        relevant_files: list[str] | None = None,
        acceptance_criteria: str = "",
        constraints: str = "",
        run_tests: bool = False,
    ) -> CodeTaskBrief:
        objective = objective.strip()
        if not objective:
            raise CodeTaskError("objective is required")

        repo_path = self._validate_repo(repo)

        brief = CodeTaskBrief(
            brief_id=str(uuid.uuid4()),
            repo=str(repo_path),
            objective=objective,
            relevant_files=[str(item).strip() for item in (relevant_files or []) if str(item).strip()],
            acceptance_criteria=acceptance_criteria.strip(),
            constraints=constraints.strip(),
            run_tests=run_tests,
            created_at=time.time(),
        )
        _BRIEFS.put(brief)
        return brief

    def get_brief(self, brief_id: str) -> CodeTaskBrief | None:
        return _BRIEFS.get(brief_id)

    def _validate_repo(self, repo: str) -> Path:
        if not repo.strip():
            raise CodeTaskError("repo is required")
        candidate = Path(repo).expanduser().resolve()
        for allowed in self.settings.code_task_allowed_dirs:
            if candidate == allowed or allowed in candidate.parents:
                return candidate
        raise CodeTaskNotAllowedError(
            f"'{candidate}' is not inside an allowed directory. "
            f"Allowed: {[str(path) for path in self.settings.code_task_allowed_dirs]}"
        )

    def write_run_script(self, brief_id: str) -> Path:
        """Generates a PowerShell script that runs the sandboxed container and
        reports the result back to Celeste. Does not execute anything; the
        user runs the returned script themselves."""
        # Validate everything before popping the brief: a fixable config error
        # (like a missing token) must not cost the user their brief.
        if not self.settings.code_task_oauth_token:
            raise CodeTaskError(
                "CELESTE_CODE_TASK_OAUTH_TOKEN is not configured. Run "
                "'claude setup-token' once and add the result to celeste-core/.env "
                "(see docs/CODE_TASK.md)."
            )

        brief = _BRIEFS.get(brief_id)
        if brief is None:
            raise CodeTaskError("Brief not found or expired; create a new one")

        prompt = brief.to_prompt()
        if "\n'@" in f"\n{prompt}" or prompt.rstrip().endswith("'@"):
            raise CodeTaskError(
                "The brief text contains a line that would break the generated "
                "script (a line consisting of just \"'@\"); rephrase it."
            )

        _BRIEFS.pop(brief_id)

        scripts_dir = Path(__file__).resolve().parents[2] / ".secrets" / "code-task-runs"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"{brief.brief_id}.ps1"

        script = f"""# Generated by Celeste code_task - review before running.
# Contains your CLAUDE_CODE_OAUTH_TOKEN; stays local, already gitignored
# under celeste-core/.secrets/. Delete this file once you no longer need it.
$ErrorActionPreference = "Stop"

$prompt = @'
{_quote_powershell_single(prompt)}
'@

$output = & docker run --rm `
    -v "{brief.repo}:/workspace" `
    -w /workspace `
    -e "CLAUDE_CODE_OAUTH_TOKEN={self.settings.code_task_oauth_token}" `
    --memory 4g --cpus 2 `
    {self.settings.code_task_image} `
    -p $prompt --output-format json --allowedTools "{_ALLOWED_TOOLS}" 2>&1
$exitCode = $LASTEXITCODE

Write-Host "----- code_task output -----"
Write-Host $output
Write-Host "----- exit code: $exitCode -----"

try {{
    $body = @{{
        brief_id = "{brief.brief_id}"
        repo = "{_quote_powershell_single(brief.repo)}"
        objective = "{_quote_powershell_single(brief.objective)}"
        acceptance_criteria = "{_quote_powershell_single(brief.acceptance_criteria)}"
        constraints = "{_quote_powershell_single(brief.constraints)}"
        exit_code = $exitCode
        output = "$output"
    }} | ConvertTo-Json
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/code-task/record" `
        -Method Post -ContentType "application/json" `
        -Headers @{{ "X-Celeste-Token" = "{self.settings.api_token}" }} `
        -Body $body | Out-Null
    Write-Host "Resultado guardado en Celeste Brain."
}} catch {{
    Write-Warning "No se pudo guardar el resultado en Celeste Brain: $_"
}}
"""
        script_path.write_text(script, encoding="utf-8")
        return script_path

    def record_result(
        self,
        *,
        brief_id: str,
        repo: str,
        objective: str,
        acceptance_criteria: str,
        constraints: str,
        exit_code: int | None,
        output: str,
    ) -> dict[str, Any]:
        """Called back by the generated script once it finishes; saves the
        outcome to Brain. Never invokes anything itself."""
        status = "completed" if exit_code == 0 else "failed"
        content = (
            f"Repositorio: {repo}\n"
            f"Objetivo: {objective}\n"
            f"Criterio de aceptacion: {acceptance_criteria or '(no especificado)'}\n"
            f"Restricciones: {constraints or '(ninguna)'}\n"
            f"Estado: {status} (codigo de salida: {exit_code})\n\n"
            f"Salida:\n{output[:4000]}"
        )
        storage = MarkdownNoteStorage(self.settings.brain_dir)
        note = storage.create(
            NoteCreate(
                title=f"code_task: {objective[:80]}",
                content=content,
                type="task",
                tags=["code_task", status],
            )
        )
        index = BrainIndex(self.settings.brain_dir, embedder=build_embedding_client(self.settings))
        index.upsert(note)
        return {"note_id": note.id, "status": status}
