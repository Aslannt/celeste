package com.aslannt.celeste.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import com.aslannt.celeste.voice.Phase
import kotlinx.coroutines.delay
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

private class Palette(val core: Color, val dots: Color, val halo: Color)

private val palettes = mapOf(
    Phase.IDLE to Palette(Color(0xFF6D28D9), Color(0xFFA78BFA), Color(0xFF4C1D95)),
    Phase.LISTENING to Palette(Color(0xFFC026D3), Color(0xFFF0ABFC), Color(0xFF86198F)),
    Phase.THINKING to Palette(Color(0xFF7C3AED), Color(0xFFC4B5FD), Color(0xFF5B21B6)),
    Phase.SPEAKING to Palette(Color(0xFF9333EA), Color(0xFFE9D5FF), Color(0xFF6B21A8)),
    Phase.ERROR to Palette(Color(0xFFBE123C), Color(0xFFFDA4AF), Color(0xFF881337)),
)

private val spin = mapOf(
    Phase.IDLE to 0.25f, Phase.LISTENING to 0.5f, Phase.THINKING to 1.6f,
    Phase.SPEAKING to 0.6f, Phase.ERROR to 0.2f,
)

private data class P3(val x: Float, val y: Float, val z: Float)

private val sphere: List<P3> = run {
    val n = 150
    val golden = PI * (3 - sqrt(5.0))
    val random = java.util.Random(7)
    List(n) { i ->
        val y = 1 - (i / (n - 1f)) * 2
        val r = sqrt(1 - y * y)
        val theta = golden * i
        val jitter = 1 + (random.nextFloat() - 0.5f) * 0.12f
        P3((cos(theta) * r * jitter).toFloat(), y * jitter, (sin(theta) * r * jitter).toFloat())
    }
}

private val links: List<Pair<Int, Int>> = buildList {
    for (i in sphere.indices) for (j in i + 1 until sphere.size) {
        val a = sphere[i]; val b = sphere[j]
        val d = sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y) + (a.z - b.z) * (a.z - b.z))
        if (d < 0.38f) add(i to j)
    }
}

/**
 * Celeste's orb: a slowly turning sphere of linked particles in purple, the
 * same design as the desktop widget. Driven by a manual frame clock (see
 * CelesteOrb for why InfiniteTransition is avoided in this project).
 */
@Composable
fun NebulaOrb(phase: Phase, level: Float, modifier: Modifier = Modifier) {
    var clock by remember { mutableFloatStateOf(0f) }
    var angle by remember { mutableFloatStateOf(0f) }
    var smooth by remember { mutableFloatStateOf(0f) }
    var mix by remember { mutableFloatStateOf(1f) }
    var from by remember { mutableFloatStateOf(0f) } // index of previous phase
    var current by remember { mutableFloatStateOf(phase.ordinal.toFloat()) }

    val currentLevel by rememberUpdatedState(level)
    LaunchedEffect(phase) {
        from = current
        current = phase.ordinal.toFloat()
        mix = 0f
    }
    LaunchedEffect(Unit) {
        var last = System.nanoTime()
        while (true) {
            val now = System.nanoTime()
            val dt = min((now - last) / 1e9f, 0.1f)
            last = now
            clock += dt
            angle += (spin[Phase.entries[current.toInt()]] ?: 0.3f) * dt
            mix = min(1f, mix + dt * 3f)
            smooth += (currentLevel - smooth) * min(1f, dt * 12f)
            delay(16)
        }
    }

    val a = palettes.getValue(Phase.entries[from.toInt()])
    val b = palettes.getValue(Phase.entries[current.toInt()])
    val core = lerp(a.core, b.core, mix)
    val dots = lerp(a.dots, b.dots, mix)
    val halo = lerp(a.halo, b.halo, mix)
    val thinking = Phase.entries[current.toInt()] == Phase.THINKING

    Canvas(modifier) {
        val cx = size.width / 2
        val cy = size.height / 2
        val breathe = if (thinking) 0.05f * sin(clock * 5) else 0.03f * sin(clock * 1.6f)
        val radius = min(size.width, size.height) * 0.30f * (1 + breathe + smooth * 0.28f)

        drawCircle(
            brush = Brush.radialGradient(
                listOf(halo.copy(alpha = 0.55f + 0.3f * smooth), halo.copy(alpha = 0.15f), Color.Transparent),
                center = Offset(cx, cy), radius = radius * 1.9f,
            ),
            radius = radius * 1.9f, center = Offset(cx, cy),
        )
        drawCircle(
            brush = Brush.radialGradient(
                listOf(lerp(core, Color.White, 0.35f).copy(alpha = 0.8f), core.copy(alpha = 0.25f), Color.Transparent),
                center = Offset(cx, cy), radius = radius * 0.9f,
            ),
            radius = radius * 0.9f, center = Offset(cx, cy),
        )

        val ay = angle
        val ax = 0.45f + 0.15f * sin(clock * 0.3f)
        val cyA = cos(ay); val syA = sin(ay); val cxA = cos(ax); val sxA = sin(ax)
        val projected = sphere.mapIndexed { i, p ->
            val wobble = 1 + smooth * 0.12f * sin(clock * 9 + i)
            var x = p.x * wobble; var y = p.y * wobble; var z = p.z * wobble
            val x2 = x * cyA + z * syA; val z2 = -x * syA + z * cyA
            x = x2; z = z2
            val y2 = y * cxA - z * sxA; val z3 = y * sxA + z * cxA
            y = y2; z = z3
            Triple(cx + x * radius, cy + y * radius, (z + 1.2f) / 2.4f)
        }
        for ((i, j) in links) {
            val (x1, y1, d1) = projected[i]
            val (x2, y2, d2) = projected[j]
            val d = (d1 + d2) / 2
            drawLine(dots.copy(alpha = 0.06f + 0.28f * d * d), Offset(x1, y1), Offset(x2, y2), strokeWidth = 1.2f)
        }
        for ((x, y, d) in projected.sortedBy { it.third }) {
            val color = if (d > 0.55f) dots else lerp(dots, Color.Black, 0.25f)
            drawCircle(color.copy(alpha = 0.28f + 0.72f * d), radius = (1.2f + 3.2f * d + smooth * 1.6f), center = Offset(x, y))
        }
        if (thinking) {
            val r = radius * 1.35f
            drawArc(
                color = dots.copy(alpha = 0.7f),
                startAngle = (-clock * 324f) % 360f, sweepAngle = 110f, useCenter = false,
                topLeft = Offset(cx - r, cy - r), size = androidx.compose.ui.geometry.Size(r * 2, r * 2),
                style = Stroke(width = 4f),
            )
        }
    }
}
