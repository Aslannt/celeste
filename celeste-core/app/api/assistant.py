from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import Settings
from app.security import require_token
from app.services.ai import AIProviderError, build_provider
from app.services.fast_paths import try_ollama_fast_path
from app.services.tools import ToolRouter


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class ToolEventResponse(BaseModel):
    tool: str
    risk: str
    status: str
    output: Any = None
    confirmation_id: str | None = None
    summary: str | None = None


class AssistantChatResponse(BaseModel):
    reply: str
    provider: str
    events: list[ToolEventResponse] = Field(default_factory=list)
    performance: dict[str, Any] | None = None


class PendingConfirmationResponse(BaseModel):
    confirmation_id: str
    tool: str
    summary: str
    created_at: float


router = APIRouter(
    prefix="/api/v1/assistant",
    tags=["assistant"],
    dependencies=[Depends(require_token)],
)


@router.get("/tools")
def list_assistant_tools() -> dict[str, list[dict[str, str]]]:
    router_service = ToolRouter(Settings.from_env())
    return {"tools": router_service.catalog()}


@router.get("/confirmations", response_model=list[PendingConfirmationResponse])
def list_pending_confirmations() -> list[PendingConfirmationResponse]:
    router_service = ToolRouter(Settings.from_env())
    return [
        PendingConfirmationResponse.model_validate(item)
        for item in router_service.pending_confirmations()
    ]


@router.get("/audit")
def list_tool_audit(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, list[dict[str, Any]]]:
    router_service = ToolRouter(Settings.from_env())
    return {"events": router_service.recent_audit(limit=limit)}


@router.post("/chat", response_model=AssistantChatResponse)
def assistant_chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    settings = Settings.from_env()
    router_service = ToolRouter(settings)

    fast_path = try_ollama_fast_path(payload.message, router_service, settings)
    if fast_path is not None:
        return AssistantChatResponse.model_validate(fast_path.to_dict())

    try:
        provider = build_provider(settings)
        result = provider.answer(payload.message, router_service)
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AssistantChatResponse.model_validate(result.to_dict())


@router.post("/confirm/{confirmation_id}", response_model=ToolEventResponse)
def confirm_assistant_action(confirmation_id: str) -> ToolEventResponse:
    router_service = ToolRouter(Settings.from_env())
    result = router_service.confirm(confirmation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confirmation not found or expired",
        )
    return ToolEventResponse.model_validate(result.to_dict())


@router.delete("/confirm/{confirmation_id}", response_model=ToolEventResponse)
def cancel_assistant_action(confirmation_id: str) -> ToolEventResponse:
    router_service = ToolRouter(Settings.from_env())
    result = router_service.cancel(confirmation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confirmation not found or expired",
        )
    return ToolEventResponse.model_validate(result.to_dict())
