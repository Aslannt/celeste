import base64
import io
import wave
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")  # extra [voice]; CI sin numpy salta estos tests
from fastapi.testclient import TestClient

import app.api.voice as voice_api
from app.main import app
from app.services.voice import VoiceError, decode_wav, speakable

TOKEN = "voice-test-token"
HEADERS = {"X-Celeste-Token": TOKEN, "Content-Type": "audio/wav"}


def _wav(seconds: float = 0.5, rate: int = 44100, channels: int = 1) -> bytes:
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi * seconds, int(rate * seconds))) * 8000).astype("<i2")
    if channels == 2:
        samples = np.repeat(samples, 2)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return buffer.getvalue()


class FakeEngine:
    def __init__(self, transcript: str):
        self.transcript = transcript
        self.spoken: list[str] = []

    def transcribe(self, audio):
        assert audio.dtype == np.float32
        return self.transcript

    def synthesize_wav(self, text: str) -> bytes:
        self.spoken.append(text)
        return b"RIFF-fake-wav"


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CELESTE_BRAIN_DIR", str(tmp_path / "CelesteBrain"))
    monkeypatch.setenv("CELESTE_API_TOKEN", TOKEN)
    monkeypatch.setenv("CELESTE_LLM_PROVIDER", "local_rules")
    return TestClient(app)


def test_decode_wav_resamples_to_16k_mono():
    audio = decode_wav(_wav(seconds=1.0, rate=44100, channels=2))
    assert audio.dtype == np.float32
    assert abs(len(audio) - 16000) <= 1


def test_decode_wav_rejects_non_wav():
    with pytest.raises(VoiceError):
        decode_wav(b"not a wav")


def test_speakable_strips_markdown():
    assert speakable("**Hola** Deivid\n- uno\n# Titulo") == "Hola Deivid\nuno\nTitulo"


def test_voice_endpoint_runs_chat_pipeline_and_returns_audio(client, monkeypatch):
    engine = FakeEngine("recuerda que el lunes pago el internet")
    monkeypatch.setattr(voice_api, "get_engine", lambda _settings: engine)

    response = client.post("/api/v1/assistant/voice", content=_wav(), headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "recuerda que el lunes pago el internet"
    assert body["reply"]
    assert base64.b64decode(body["audio_wav_base64"]) == b"RIFF-fake-wav"
    assert engine.spoken == [body["reply"]]
    assert "stt_ms" in body["performance"] and "tts_ms" in body["performance"]


def test_voice_endpoint_can_skip_audio(client, monkeypatch):
    monkeypatch.setattr(voice_api, "get_engine", lambda _settings: FakeEngine("hola"))

    body = client.post("/api/v1/assistant/voice?speak=false", content=_wav(), headers=HEADERS).json()

    assert body["audio_wav_base64"] is None


def test_voice_endpoint_handles_silence(client, monkeypatch):
    monkeypatch.setattr(voice_api, "get_engine", lambda _settings: FakeEngine(""))

    body = client.post("/api/v1/assistant/voice", content=_wav(), headers=HEADERS).json()

    assert body["provider"] == "voice"
    assert "No te entendi" in body["reply"]


def test_voice_endpoint_disabled_returns_503(client, monkeypatch):
    monkeypatch.setenv("CELESTE_VOICE_ENABLED", "false")

    response = client.post("/api/v1/assistant/voice", content=_wav(), headers=HEADERS)

    assert response.status_code == 503


def test_voice_endpoint_rejects_empty_and_bad_audio(client, monkeypatch):
    monkeypatch.setattr(voice_api, "get_engine", lambda _settings: FakeEngine("hola"))

    assert client.post("/api/v1/assistant/voice", content=b"", headers=HEADERS).status_code == 400
    assert client.post("/api/v1/assistant/voice", content=b"xx", headers=HEADERS).status_code == 400


def test_voice_endpoint_requires_token(client):
    response = client.post("/api/v1/assistant/voice", content=_wav(), headers={"Content-Type": "audio/wav"})
    assert response.status_code in (401, 403)
