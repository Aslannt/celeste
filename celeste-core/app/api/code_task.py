from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings
from app.security import require_token
from app.services.code_task import CodeTaskError, CodeTaskNotAllowedError, CodeTaskRunner

router = APIRouter(
    prefix="/api/v1/code-task",
    tags=["code-task"],
    dependencies=[Depends(require_token)],
)


class CodeTaskBriefRequest(BaseModel):
    repo: str = Field(min_length=1, max_length=500)
    objective: str = Field(min_length=1, max_length=4000)
    relevant_files: list[str] = Field(default_factory=list)
    acceptance_criteria: str = Field(default="", max_length=2000)
    constraints: str = Field(default="", max_length=2000)
    run_tests: bool = False


class CodeTaskRecordRequest(BaseModel):
    brief_id: str
    repo: str
    objective: str
    acceptance_criteria: str = ""
    constraints: str = ""
    exit_code: int | None = None
    output: str = ""


@router.post("/brief")
def create_brief(request: CodeTaskBriefRequest) -> dict[str, Any]:
    """Human-triggered only: not reachable through /assistant/chat or any
    Tool Router tool. See ADR-011."""
    runner = CodeTaskRunner(Settings.from_env())
    try:
        brief = runner.create_brief(
            repo=request.repo,
            objective=request.objective,
            relevant_files=request.relevant_files,
            acceptance_criteria=request.acceptance_criteria,
            constraints=request.constraints,
            run_tests=request.run_tests,
        )
    except CodeTaskNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except CodeTaskError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return brief.to_dict()


@router.post("/prepare/{brief_id}")
def prepare_run(brief_id: str) -> dict[str, Any]:
    """Writes a ready-to-run sandboxed script; Celeste never executes it.
    The user reviews and runs it themselves in their own terminal."""
    runner = CodeTaskRunner(Settings.from_env())
    try:
        script_path = runner.write_run_script(brief_id)
    except CodeTaskError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "script_path": str(script_path),
        "instructions": (
            "Revisa el script y luego correlo tu mismo: "
            f'powershell -ExecutionPolicy Bypass -File "{script_path}"'
        ),
    }


@router.post("/record")
def record_result(request: CodeTaskRecordRequest) -> dict[str, Any]:
    """Called back by the generated script once it finishes running. Only
    saves the outcome to Brain; does not invoke anything."""
    runner = CodeTaskRunner(Settings.from_env())
    try:
        return runner.record_result(
            brief_id=request.brief_id,
            repo=request.repo,
            objective=request.objective,
            acceptance_criteria=request.acceptance_criteria,
            constraints=request.constraints,
            exit_code=request.exit_code,
            output=request.output,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save code_task result to Brain: {exc}",
        ) from exc
