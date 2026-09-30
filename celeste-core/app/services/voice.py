"""Local speech for remote clients (Android): Whisper in, Piper out, on this PC.

The phone only records and plays audio; transcription and synthesis happen
here, on the user's own machine and GPU. No audio goes to Google or any cloud
service, and the voice is the same Piper voice as the desktop orb.

Optional feature (``CELESTE_VOICE_ENABLED``): the heavy dependencies
(faster-whisper, piper-tts, numpy) live in the ``[voice]`` extra and are only
imported when the first voice request arrives.
"""

from __future__ import annotations

import glob
import io
import os
import re
import site
import threading
import wave
from typing import Any

from app.config import Settings

WHISPER_RATE = 16000
_ENGINE_LOCK = threading.Lock()
_engine: "VoiceEngine | None" = None
_MARKDOWN_RE = re.compile(r"(\*\*|__|`|^#+\s*|^\s*[-*]\s+)", re.MULTILINE)
_INITIAL_PROMPT = "Celeste, Deivid, Verónica, R15, APX, BBVA, MuleSoft, Obsidian."


class VoiceError(RuntimeError):
    pass


class VoiceUnavailableError(VoiceError):
    pass


def _expose_cuda_dlls() -> None:
    """CUDA DLLs come from pip wheels (nvidia-cublas/cudnn); Windows doesn't see them alone."""
    if os.name != "nt":
        return
    for base in site.getsitepackages():
        for d in glob.glob(os.path.join(base, "Lib", "site-packages", "nvidia", "*", "bin")) + glob.glob(
            os.path.join(base, "nvidia", "*", "bin")
        ):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


def decode_wav(data: bytes) -> Any:
    """16-bit PCM WAV (any rate, mono or stereo) -> float32 mono at 16 kHz."""
    import numpy as np

    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as exc:
        raise VoiceError("El audio debe ser WAV PCM de 16 bits.") from exc
    if width != 2:
        raise VoiceError("El audio debe ser WAV PCM de 16 bits.")
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != WHISPER_RATE and len(audio):
        positions = np.arange(0, len(audio), rate / WHISPER_RATE)
        audio = np.interp(positions, np.arange(len(audio)), audio).astype(np.float32)
    return audio


def speakable(text: str) -> str:
    """Drop markdown so the voice doesn't read asterisks or hashes, and keep it compact."""
    text = _MARKDOWN_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


class VoiceEngine:
    def __init__(self, whisper_model: str, piper_model: str):
        try:
            _expose_cuda_dlls()
            from faster_whisper import WhisperModel
            from piper import PiperVoice
        except ImportError as exc:
            raise VoiceUnavailableError(
                "Faltan las dependencias de voz. Instala: pip install -e \".[voice]\""
            ) from exc
        try:
            self.whisper = WhisperModel(whisper_model, device="cuda", compute_type="float16")
        except Exception:  # noqa: BLE001 - no usable GPU: smaller model on CPU
            self.whisper = WhisperModel("small", device="cpu", compute_type="int8")
        self.voice = PiperVoice.load(piper_model)
        self.rate = int(self.voice.config.sample_rate)
        self._lock = threading.Lock()

    def transcribe(self, audio: Any) -> str:
        with self._lock:
            segments, _ = self.whisper.transcribe(
                audio, language="es", beam_size=1, vad_filter=True, initial_prompt=_INITIAL_PROMPT
            )
            return " ".join(s.text.strip() for s in segments).strip()

    def synthesize_wav(self, text: str) -> bytes:
        import numpy as np

        with self._lock:
            chunks = [c.audio_float_array for c in self.voice.synthesize(speakable(text))]
        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
        # 300 ms of silence first: Bluetooth/USB outputs swallow the first word otherwise.
        audio = np.concatenate([np.zeros(int(self.rate * 0.3), dtype=np.float32), audio])
        pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.rate)
            wav.writeframes(pcm)
        return buffer.getvalue()


def get_engine(settings: Settings) -> VoiceEngine:
    """Lazy singleton: models load on the first voice request, then stay warm."""
    global _engine
    if not settings.voice_enabled:
        raise VoiceUnavailableError("La voz del Core esta desactivada (CELESTE_VOICE_ENABLED=false).")
    if settings.voice_piper_model is None or not settings.voice_piper_model.exists():
        raise VoiceUnavailableError("Falta la voz de Piper (CELESTE_VOICE_PIPER_MODEL).")
    with _ENGINE_LOCK:
        if _engine is None:
            _engine = VoiceEngine(settings.voice_whisper_model, str(settings.voice_piper_model))
        return _engine
