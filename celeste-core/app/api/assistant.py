from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings
from app.security import require_token
from app.services.ai import AIProviderError, build_provider
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


router = APIRouter(
    prefix="/api/v1/assistant",
    tags=["assistant"],
    dependencies=[Depends(require_token)],
)


@router.get("/tools")
def list_assistant_tools() -> dict[str, list[dict[str, str]]]:
    router_service = ToolRouter(Settings.from_env())
    return {"tools": router_service.catalog()}


@router.post("/chat", response_model=AssistantChatResponse)
def assistant_chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    settings = Settings.from_env()
    router_service = ToolRouter(settings)
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
