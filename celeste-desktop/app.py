"""Widget de escritorio de Celeste: un orbe morado flotante; un clic y hablas.

Flujo: clic -> graba (corta solo al callar) -> Whisper local -> Core /assistant/chat
-> Piper local lee la respuesta. Un segundo clic corta la grabación o calla a Celeste.
Clic derecho: nueva conversación / salir. Arrastrar: mover el orbe.
"""

from __future__ import annotations

import os
import re
import sys
import datetime as dt
import threading
import unicodedata
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, QPoint, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QCursor, QDesktopServices
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QVBoxLayout, QWidget

import desktop_pin
from orb import Orb
from voice import Recorder, SpeechToText, TextToSpeech, find_input_device

HERE = Path(__file__).resolve().parent


def load_config() -> dict[str, str]:
    cfg: dict[str, str] = {}
    for env_file in (HERE / ".env", HERE.parent / "celeste-core" / ".env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    cfg.setdefault(key.strip(), value.strip())
    cfg.update({k: v for k, v in os.environ.items() if k.startswith("CELESTE_")})
    return cfg


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


YES = re.compile(r"\b(si|confirmo|confirma|dale|hazlo|claro|de una|adelante)\b")
NO = re.compile(r"\b(no|cancela|cancelar|olvidalo|dejalo)\b")


def _k(tokens: int) -> str:
    return f"{tokens / 1000:.1f}k" if tokens >= 1000 else str(tokens)


class Bus(QObject):
    state = Signal(str)
    caption = Signal(str)
    level = Signal(float)
    speak_done = Signal()
    badge = Signal(str, bool)  # texto, ¿usó Claude?


class CelesteWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = load_config()
        self.base_url = self.cfg.get("CELESTE_URL", "http://127.0.0.1:8000").rstrip("/")
        self.http = httpx.Client(
            base_url=self.base_url,
            headers={"X-Celeste-Token": self.cfg.get("CELESTE_API_TOKEN", "")},
            timeout=180,
        )
        self.bus = Bus()
        self.stt: SpeechToText | None = None
        self.tts: TextToSpeech | None = None
        self.recorder: Recorder | None = None
        self.state = "loading"
        self.pending_confirmation: str | None = None
        self._press: QPoint | None = None
        self._dragged = False

        # Widget de escritorio: sin "siempre visible"; desktop_pin lo ancla al escritorio.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(320, 520)  # alto de sobra para respuestas largas; lo transparente no estorba

        self.orb = Orb(self)
        self.orb.setFixedSize(220, 220)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(
            "QLabel { color: #f3e8ff; background: rgba(30, 16, 54, 190); border: 1px solid rgba(167,139,250,90);"
            " border-radius: 10px; padding: 6px 10px; font: 10pt 'Segoe UI'; }"
        )
        self.label.hide()
        # Etiqueta chica bajo el subtítulo: ¿esta respuesta gastó Claude o fue local?
        self.badge = QLabel(self)
        self.badge.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.orb, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        layout.addSpacing(4)
        layout.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        layout.addStretch()
        self.label.setMaximumWidth(310)

        self.bus.state.connect(self._set_state)
        self.bus.caption.connect(self._show_caption)
        self.bus.level.connect(lambda v: setattr(self.orb, "level", v))
        self.bus.speak_done.connect(self._after_speaking)
        self.bus.badge.connect(self._show_badge)

        self.hide_caption = QTimer(self, singleShot=True, timeout=self._hide_captions)
        self.frame = QTimer(self, interval=16, timeout=self._tick)
        self.frame.start()

        settings = QSettings("Celeste", "DesktopWidget")
        pos = settings.value("pos")
        if isinstance(pos, QPoint):
            self.move(pos)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 20)

        self.setToolTip("Celeste · clic para hablar · clic derecho para opciones")
        # Revisa cada 2 s que siga anclada (p. ej. si Explorer se reinició).
        self.pin_guard = QTimer(self, interval=2000, timeout=lambda: desktop_pin.keep_pinned(int(self.winId())))
        threading.Thread(target=self._load_models, daemon=True).start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Qt fija el dueño de la ventana al terminar de mostrarla; anclar justo después.
        QTimer.singleShot(150, lambda: desktop_pin.pin(int(self.winId())))
        self.pin_guard.start()

    # ---------- carga ----------
    def _load_models(self) -> None:
        self.bus.caption.emit("Despertando…")
        try:
            voice = HERE / "voices" / f"{self.cfg.get('CELESTE_VOICE', 'es_MX-claude-high')}.onnx"
            self.tts = TextToSpeech(voice)
            self.stt = SpeechToText(self.cfg.get("CELESTE_WHISPER_MODEL", "large-v3-turbo"))
            device = find_input_device(self.cfg.get("CELESTE_MIC"))
            self.recorder = Recorder(device, on_level=self.bus.level.emit)
        except Exception as exc:  # noqa: BLE001 - mostrarlo en el orbe, no crashear
            self.bus.state.emit("error")
            self.bus.caption.emit(f"No pude cargar la voz: {exc}")
            return
        self.bus.state.emit("idle")
        self.bus.caption.emit("Lista. Haz clic para hablar.")

    # ---------- UI ----------
    def _set_state(self, state: str) -> None:
        self.state = state
        self.orb.set_state(state)

    def _show_caption(self, text: str) -> None:
        self.label.setText(text)
        # Con word-wrap, adjustSize() encoge la etiqueta y corta el texto: fijar ancho real.
        width = min(310, self.label.fontMetrics().horizontalAdvance(text) + 30)
        width = max(width, 80)
        self.label.setFixedWidth(width)
        # Alto exacto para el texto envuelto (con word-wrap Qt lo subestima y corta la última línea).
        self.label.setFixedHeight(self.label.heightForWidth(width) + 4)
        self.label.show()
        self.hide_caption.start(9000 if self.state in ("idle", "error") else 60000)

    def _hide_captions(self) -> None:
        self.label.hide()
        self.badge.hide()

    def _show_badge(self, text: str, used_claude: bool) -> None:
        color = "#c4b5fd" if used_claude else "#86efac"
        self.badge.setStyleSheet(
            f"QLabel {{ color: {color}; background: rgba(20, 12, 36, 170); border-radius: 8px;"
            " padding: 2px 8px; font: 8pt 'Segoe UI'; }"
        )
        self.badge.setText(text)
        self.badge.adjustSize()
        self.badge.show()

    # ---------- uso ----------
    @staticmethod
    def _usage_key(field: str) -> str:
        return f"usage/{dt.date.today().isoformat()}/{field}"

    def _record_usage(self, used_claude: bool, tokens: int) -> None:
        settings = QSettings("Celeste", "DesktopWidget")
        field = "claude" if used_claude else "local"
        settings.setValue(self._usage_key(field), int(settings.value(self._usage_key(field), 0)) + 1)
        if used_claude:
            settings.setValue(self._usage_key("tokens"), int(settings.value(self._usage_key("tokens"), 0)) + tokens)

    def _usage_today(self) -> str:
        settings = QSettings("Celeste", "DesktopWidget")
        claude = int(settings.value(self._usage_key("claude"), 0))
        local = int(settings.value(self._usage_key("local"), 0))
        tokens = int(settings.value(self._usage_key("tokens"), 0))
        return f"Hoy: {claude} con Claude ({_k(tokens)} tokens) · {local} locales"

    def _tick(self) -> None:
        if self.state == "speaking" and self.tts is not None:
            self.orb.level = self.tts.level()
            if not self.tts.is_playing():
                self.bus.speak_done.emit()
        elif self.state == "thinking":
            self.orb.level = 0.0
        self.orb.tick()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragged = False

    def mouseMoveEvent(self, event) -> None:
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            target = event.globalPosition().toPoint() - self._press
            if (target - self.pos()).manhattanLength() > 4 or self._dragged:
                self._dragged = True
                self.move(target)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        desktop_pin.to_bottom(int(self.winId()))
        if self._dragged:
            QSettings("Celeste", "DesktopWidget").setValue("pos", self.pos())
        else:
            self.on_click()
        self._press = None

    def contextMenuEvent(self, _event) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #1e1036; color: #f3e8ff; } QMenu::item:selected { background: #6d28d9; }")
        usage = QAction(self._usage_today(), self)
        usage.setEnabled(False)
        limits = QAction("Ver mis límites de Claude…", self, triggered=lambda: QDesktopServices.openUrl(
            QUrl("https://claude.ai/settings/usage")))
        reset = QAction("Nueva conversación", self, triggered=self._reset_conversation)
        quit_ = QAction("Salir", self, triggered=QApplication.quit)
        menu.addAction(usage)
        menu.addAction(limits)
        menu.addSeparator()
        menu.addAction(reset)
        menu.addSeparator()
        menu.addAction(quit_)
        menu.exec(QCursor.pos())
        desktop_pin.to_bottom(int(self.winId()))

    # ---------- flujo ----------
    def on_click(self) -> None:
        if self.state in ("idle", "error") and self.recorder is not None:
            self._listen()
        elif self.state == "listening" and self.recorder is not None:
            self.recorder.stop()
        elif self.state == "speaking" and self.tts is not None:
            self.tts.stop()

    def _listen(self) -> None:
        self.badge.hide()
        self._set_state("listening")
        self._show_caption("Te escucho…")
        threading.Thread(target=self._pipeline, daemon=True).start()

    def _pipeline(self) -> None:
        assert self.recorder and self.stt
        audio = self.recorder.record()
        if audio is None:
            self.bus.state.emit("idle")
            if self.recorder.dead_mic:
                self.bus.state.emit("error")
                self.bus.caption.emit(f"Tu micrófono no da señal ({self.recorder.device_name}). "
                                      "Revisa que esté conectado o elige otro con CELESTE_MIC.")
            else:
                self.bus.caption.emit("No te escuché.")
            return
        self.bus.state.emit("thinking")
        text = self.stt.transcribe(audio)
        if not text:
            self.bus.state.emit("idle")
            self.bus.caption.emit("No te entendí.")
            return
        self.bus.caption.emit(f"“{text}”")

        if self.pending_confirmation:
            reply = self._resolve_confirmation(text)
        else:
            reply = self._chat(text)
        self._say(reply)

    def _chat(self, text: str) -> str:
        try:
            response = self.http.post("/api/v1/assistant/chat", json={"message": text})
            if response.status_code == 503:
                return "No pude pensar ahora mismo. " + str(response.json().get("detail", ""))[:120]
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError:
            return "No encuentro el Core de Celeste. ¿Está encendido?"
        except Exception as exc:  # noqa: BLE001
            return f"Algo falló hablando con el Core: {type(exc).__name__}."
        for event in data.get("events") or []:
            if event.get("status") == "confirmation_required" and event.get("confirmation_id"):
                self.pending_confirmation = event["confirmation_id"]
        self._report_source(data)
        return str(data.get("reply") or "No obtuve respuesta.")

    def _report_source(self, data: dict) -> None:
        performance = data.get("performance") or {}
        rounds = performance.get("claude_rounds") or []
        if data.get("provider") == "claude" and rounds:
            tokens = sum(int(r.get("input_tokens", 0)) + int(r.get("output_tokens", 0)) for r in rounds)
            seconds = float(performance.get("total_ms") or 0) / 1000
            self._record_usage(True, tokens)
            self.bus.badge.emit(f"● Claude · {_k(tokens)} tokens · {seconds:.1f} s", True)
        else:
            self._record_usage(False, 0)
            self.bus.badge.emit("● Local · 0 tokens", False)

    def _resolve_confirmation(self, text: str) -> str:
        confirmation_id, self.pending_confirmation = self.pending_confirmation, None
        plain = _plain(text)
        try:
            self.bus.badge.emit("● Local · 0 tokens", False)
            if NO.search(plain):
                self.http.delete(f"/api/v1/assistant/confirm/{confirmation_id}")
                return "Cancelado."
            if YES.search(plain):
                result = self.http.post(f"/api/v1/assistant/confirm/{confirmation_id}").json()
                return "Hecho. " + str(result.get("summary") or "")
        except Exception:  # noqa: BLE001
            return "No pude completar la confirmación."
        self.http.delete(f"/api/v1/assistant/confirm/{confirmation_id}")
        return "No entendí si sí o no, así que lo cancelé por seguridad."

    def _say(self, text: str) -> None:
        self.bus.caption.emit(text)
        assert self.tts
        try:
            self.tts.speak(text)
            self.bus.state.emit("speaking")
        except Exception:  # noqa: BLE001
            self.bus.state.emit("idle")

    def _after_speaking(self) -> None:
        if self.state != "speaking":
            return
        if self.pending_confirmation:
            self._listen()  # espera el "sí" / "no" sin otro clic
        else:
            self._set_state("idle")
            self.hide_caption.start(9000)

    def _reset_conversation(self) -> None:
        try:
            self.http.delete("/api/v1/assistant/conversation")
            self._show_caption("Conversación nueva.")
        except Exception:  # noqa: BLE001
            self._show_caption("No encuentro el Core.")


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    widget = CelesteWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
