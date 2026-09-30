from __future__ import annotations

import base64
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.assistant import ToolEventResponse, run_chat
from app.config import Settings
from app.security import require_token
from app.services.voice import VoiceError, VoiceUnavailableError, decode_wav, get_engine, speakable

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # ~5 min of 16 kHz mono PCM


class VoiceResponse(BaseModel):
    transcript: str
    reply: str
    provider: str
    events: list[ToolEventResponse] = Field(default_factory=list)
    performance: dict[str, Any] | None = None
    audio_wav_base64: str | None = None


router = APIRouter(
    prefix="/api/v1/assistant",
    tags=["voice"],
    dependencies=[Depends(require_token)],
)


@router.get("/voice/status")
def voice_status() -> dict[str, Any]:
    settings = Settings.from_env()
    piper = settings.voice_piper_model
    return {
        "enabled": settings.voice_enabled,
        "whisper_model": settings.voice_whisper_model,
        "piper_model_present": bool(piper and piper.exists()),
    }


@router.post("/voice", response_model=VoiceResponse)
async def assistant_voice(
    request: Request,
    speak: bool = Query(default=True, description="Devolver la respuesta tambien como audio WAV."),
) -> VoiceResponse:
    """WAV (16-bit PCM) in -> Whisper -> same pipeline as /chat -> Piper WAV out."""
    data = await request.body()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Falta el audio (cuerpo WAV).")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio demasiado largo.")
    settings = Settings.from_env()
    try:
        engine = await run_in_threadpool(get_engine, settings)
        audio = decode_wav(data)
    except VoiceUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except VoiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    started = time.perf_counter()
    transcript = await run_in_threadpool(engine.transcribe, audio)
    stt_ms = round((time.perf_counter() - started) * 1000, 1)

    if not transcript:
        reply, provider, events, performance = "No te entendi. Intentalo de nuevo.", "voice", [], {}
    else:
        chat = await run_in_threadpool(run_chat, transcript)
        reply, provider = speakable(chat.reply), chat.provider  # plain text: shown and spoken
        events, performance = chat.events, dict(chat.performance or {})
    performance["stt_ms"] = stt_ms

    audio_b64 = None
    if speak:
        started = time.perf_counter()
        wav = await run_in_threadpool(engine.synthesize_wav, reply)
        performance["tts_ms"] = round((time.perf_counter() - started) * 1000, 1)
        audio_b64 = base64.b64encode(wav).decode("ascii")

    return VoiceResponse(
        transcript=transcript,
        reply=reply,
        provider=provider,
        events=events,
        performance=performance,
        audio_wav_base64=audio_b64,
    )
