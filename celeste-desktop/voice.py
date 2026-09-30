"""Voz 100% local: micrófono con corte automático por silencio, Whisper en GPU y Piper.

Nada de audio sale de la máquina. Lo único que viaja al Core es el texto transcrito.
"""

from __future__ import annotations

import glob
import os
import queue
import site
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 480  # 30 ms


def _expose_cuda_dlls() -> None:
    """Las DLL de CUDA vienen de pip (nvidia-cublas/cudnn); Windows no las ve solo."""
    for base in site.getsitepackages():
        for d in glob.glob(os.path.join(base, "Lib", "site-packages", "nvidia", "*", "bin")) + glob.glob(
            os.path.join(base, "nvidia", "*", "bin")
        ):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


def find_input_device(name_hint: str | None) -> int | None:
    if not name_hint:
        return None
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and name_hint.lower() in dev["name"].lower():
            return idx
    return None


class Recorder:
    """Graba hasta que el usuario calla (~1 s de silencio) o vuelve a hacer clic."""

    def __init__(self, device: int | None, on_level, silence_s: float = 1.0, max_s: float = 25.0, no_speech_s: float = 6.0):
        self.device = device
        self.on_level = on_level
        self.silence_s = silence_s
        self.max_s = max_s
        self.no_speech_s = no_speech_s
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def record(self) -> np.ndarray | None:
        self._stop.clear()
        chunks: list[np.ndarray] = []
        q: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata, _frames, _time, _status):
            q.put(indata[:, 0].copy())

        noise: list[float] = []
        speech_started = False
        last_voice = started = time.monotonic()
        with sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, channels=1, dtype="float32",
                            device=self.device, callback=callback):
            while not self._stop.is_set():
                try:
                    block = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                chunks.append(block)
                rms = float(np.sqrt(np.mean(block * block)) + 1e-9)
                now = time.monotonic()
                if len(noise) < 10:  # primeros 300 ms: piso de ruido
                    noise.append(rms)
                threshold = max(0.012, (sum(noise) / len(noise)) * 3.0)
                self.on_level(min(1.0, rms / (threshold * 4)))
                if rms > threshold:
                    speech_started = True
                    last_voice = now
                if speech_started and now - last_voice > self.silence_s:
                    break
                if not speech_started and now - started > self.no_speech_s:
                    return None
                if now - started > self.max_s:
                    break
        self.on_level(0.0)
        if not speech_started:
            return None
        return np.concatenate(chunks)


class SpeechToText:
    def __init__(self, model: str = "large-v3-turbo"):
        _expose_cuda_dlls()
        from faster_whisper import WhisperModel

        try:
            self.model = WhisperModel(model, device="cuda", compute_type="float16")
        except Exception:
            # Sin GPU usable: CPU con un modelo más chico para no perder velocidad.
            self.model = WhisperModel("small", device="cpu", compute_type="int8")
        # Calentar para que el primer comando real no pague la inicialización.
        self.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32))

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language="es",
            beam_size=1,
            vad_filter=True,
            initial_prompt="Celeste, Deivid, Verónica, R15, APX, BBVA, MuleSoft, Obsidian.",
        )
        return " ".join(s.text.strip() for s in segments).strip()


class TextToSpeech:
    def __init__(self, voice_path: Path):
        from piper import PiperVoice

        self.voice = PiperVoice.load(str(voice_path))
        self.rate = self.voice.config.sample_rate
        self._playing_until = 0.0
        self._envelope: np.ndarray = np.zeros(1)
        self._started = 0.0

    def speak(self, text: str) -> None:
        """Reproduce sin bloquear; `level()` da la amplitud actual para animar el orbe."""
        audio = np.concatenate([c.audio_float_array for c in self.voice.synthesize(text)])
        frame = int(self.rate * 0.03)
        pad = (-len(audio)) % frame
        env = np.sqrt(np.mean(np.pad(audio, (0, pad)).reshape(-1, frame) ** 2, axis=1))
        self._envelope = np.clip(env / (env.max() + 1e-6), 0, 1)
        sd.play(audio, self.rate)
        self._started = time.monotonic()
        self._playing_until = self._started + len(audio) / self.rate

    def is_playing(self) -> bool:
        return time.monotonic() < self._playing_until

    def level(self) -> float:
        if not self.is_playing():
            return 0.0
        idx = int((time.monotonic() - self._started) / 0.03)
        return float(self._envelope[min(idx, len(self._envelope) - 1)])

    def stop(self) -> None:
        sd.stop()
        self._playing_until = 0.0
