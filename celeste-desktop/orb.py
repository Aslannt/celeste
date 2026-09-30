"""Orbe animado de Celeste: esfera de partículas enlazadas, en morado, que gira y respira.

Solo dibuja. El estado (idle/listening/thinking/speaking/...) y el nivel de audio
los fija la ventana desde afuera.
"""

from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

# Paleta por estado: (núcleo, partículas, halo)
PALETTES = {
    "loading": ("#3b2a5c", "#6d5a8f", "#2a1d44"),
    "idle": ("#6d28d9", "#a78bfa", "#4c1d95"),
    "listening": ("#c026d3", "#f0abfc", "#86198f"),
    "thinking": ("#7c3aed", "#c4b5fd", "#5b21b6"),
    "speaking": ("#9333ea", "#e9d5ff", "#6b21a8"),
    "error": ("#be123c", "#fda4af", "#881337"),
}

# Velocidad de giro (rad/s) por estado
SPIN = {"loading": 0.15, "idle": 0.25, "listening": 0.5, "thinking": 1.6, "speaking": 0.6, "error": 0.2}


def _fibonacci_sphere(n: int) -> list[tuple[float, float, float]]:
    points = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - (i / (n - 1)) * 2
        r = math.sqrt(1 - y * y)
        theta = golden * i
        jitter = 1 + random.uniform(-0.06, 0.06)
        points.append((math.cos(theta) * r * jitter, y * jitter, math.sin(theta) * r * jitter))
    return points


class Orb(QWidget):
    def __init__(self, parent: QWidget | None = None, particles: int = 170):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.points = _fibonacci_sphere(particles)
        # Enlaces entre vecinos cercanos, precalculados una vez
        self.links = [
            (i, j)
            for i in range(len(self.points))
            for j in range(i + 1, len(self.points))
            if math.dist(self.points[i], self.points[j]) < 0.36
        ]
        self.state = "loading"
        self.level = 0.0          # 0..1, nivel de audio externo (mic o voz)
        self._smooth = 0.0
        self._angle = 0.0
        self._last = time.perf_counter()
        self._colors = {k: tuple(QColor(c) for c in v) for k, v in PALETTES.items()}
        self._mix = 1.0
        self._from = self.state

    def set_state(self, state: str) -> None:
        if state != self.state:
            self._from, self.state, self._mix = self.state, state, 0.0

    def tick(self) -> None:
        now = time.perf_counter()
        dt = min(now - self._last, 0.1)
        self._last = now
        self._angle += SPIN.get(self.state, 0.3) * dt
        self._smooth += (self.level - self._smooth) * min(1.0, dt * 12)
        self._mix = min(1.0, self._mix + dt * 3)
        self.update()

    def _color(self, idx: int) -> QColor:
        a = self._colors[self._from][idx]
        b = self._colors[self.state][idx]
        m = self._mix
        return QColor(
            int(a.red() + (b.red() - a.red()) * m),
            int(a.green() + (b.green() - a.green()) * m),
            int(a.blue() + (b.blue() - a.blue()) * m),
        )

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        t = time.perf_counter()

        breathe = 0.03 * math.sin(t * 1.6)
        if self.state == "thinking":
            breathe = 0.05 * math.sin(t * 5)
        scale = 1 + breathe + self._smooth * 0.28
        radius = min(w, h) * 0.30 * scale

        core, dots, halo = self._color(0), self._color(1), self._color(2)

        # Halo
        glow = QRadialGradient(QPointF(cx, cy), radius * 1.9)
        c0 = QColor(halo); c0.setAlpha(int(150 + 80 * self._smooth))
        c1 = QColor(halo); c1.setAlpha(40)
        c2 = QColor(halo); c2.setAlpha(0)
        glow.setColorAt(0.0, c0); glow.setColorAt(0.45, c1); glow.setColorAt(1.0, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), radius * 1.9, radius * 1.9)

        # Núcleo brillante
        inner = QRadialGradient(QPointF(cx, cy), radius * 0.9)
        k0 = QColor(core).lighter(160); k0.setAlpha(200)
        k1 = QColor(core); k1.setAlpha(60)
        k2 = QColor(core); k2.setAlpha(0)
        inner.setColorAt(0, k0); inner.setColorAt(0.5, k1); inner.setColorAt(1, k2)
        p.setBrush(inner)
        p.drawEllipse(QPointF(cx, cy), radius * 0.9, radius * 0.9)

        # Proyección 3D de las partículas
        ay, ax = self._angle, 0.45 + 0.15 * math.sin(t * 0.3)
        cos_y, sin_y, cos_x, sin_x = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
        projected = []
        for i, (x, y, z) in enumerate(self.points):
            wobble = 1 + self._smooth * 0.12 * math.sin(t * 9 + i)
            x, y, z = x * wobble, y * wobble, z * wobble
            x, z = x * cos_y + z * sin_y, -x * sin_y + z * cos_y
            y, z = y * cos_x - z * sin_x, y * sin_x + z * cos_x
            depth = (z + 1.2) / 2.4  # 0 atrás .. 1 adelante
            projected.append((cx + x * radius, cy + y * radius, depth))

        # Enlaces
        for i, j in self.links:
            x1, y1, d1 = projected[i]
            x2, y2, d2 = projected[j]
            d = (d1 + d2) / 2
            lc = QColor(dots); lc.setAlpha(int(15 + 70 * d * d))
            p.setPen(QPen(lc, 0.8))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Partículas (de atrás hacia adelante)
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, d in sorted(projected, key=lambda q: q[2]):
            pc = QColor(dots) if d > 0.55 else QColor(dots).darker(130)
            pc.setAlpha(int(70 + 185 * d))
            p.setBrush(pc)
            s = 0.8 + 2.2 * d + self._smooth * 1.2
            p.drawEllipse(QPointF(x, y), s, s)

        # Anillo orbital mientras piensa
        if self.state == "thinking":
            ring = QColor(dots); ring.setAlpha(170)
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            r = radius * 1.35
            start = int((-t * 360 * 0.9) % 360 * 16)
            p.drawArc(int(cx - r), int(cy - r), int(2 * r), int(2 * r), start, 110 * 16)
        p.end()
