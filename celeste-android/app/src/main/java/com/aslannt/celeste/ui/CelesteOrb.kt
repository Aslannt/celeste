package com.aslannt.celeste.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlin.math.min
import kotlin.math.sin

/** Mirrors the states the web UI orb (celeste-core/web/index.html) reacts to. */
enum class OrbState { IDLE, LISTENING, THINKING, SPEAKING }

private val cyan = Color(0xFF4FD6FF)
private val amber = Color(0xFFFFB84F)

/**
 * Animated "Jarvis-style" orb: a rotating glow ring plus a pulsing core. Reacts
 * to [state] the same way the web client's canvas orb does, so the visual
 * language stays consistent across devices.
 *
 * Driven entirely by a manual frame clock rather than Compose's
 * InfiniteTransition: in this Kotlin/Compose version combination,
 * InfiniteTransition.animateValue/animateFloat exist in the compiled
 * artifact but fail to resolve at the Kotlin compiler level ("Unresolved
 * reference") - a metadata mismatch, not a missing API. Plain state +
 * LaunchedEffect avoids it entirely.
 */
@Composable
fun CelesteOrb(state: OrbState, modifier: Modifier = Modifier) {
    val color = if (state == OrbState.THINKING) amber else cyan

    var clockMillis by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        val start = System.nanoTime()
        while (true) {
            clockMillis = (System.nanoTime() - start) / 1_000_000f
            delay(16)
        }
    }

    val rotation = (clockMillis / 9000f * 360f) % 360f

    val active = state != OrbState.IDLE
    val period = if (active) 260f else 1800f
    val phase = (clockMillis % period) / period
    val pulse = (sin(phase * 2 * Math.PI.toFloat()) + 1f) / 2f
    val targetLevel = if (active) 0.35f + 0.45f * pulse else 0.08f + 0.05f * pulse
    val level by animateFloatAsState(targetValue = targetLevel, label = "level")

    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(220.dp)) {
            val base = min(size.width, size.height) * 0.22f
            val cx = size.width / 2
            val cy = size.height / 2

            for (ring in 0 until 3) {
                val r = base + ring * 20f + level * 46f
                val direction = if (ring % 2 == 0) 1f else -1f
                val startAngle = rotation * direction + ring * 40f
                drawArc(
                    color = color.copy(alpha = 0.38f - ring * 0.09f),
                    startAngle = startAngle,
                    sweepAngle = 250f,
                    useCenter = false,
                    topLeft = Offset(cx - r, cy - r),
                    size = Size(r * 2, r * 2),
                    style = Stroke(width = 3f),
                )
            }

            val glowRadius = base * (0.55f + level * 0.55f)
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(color.copy(alpha = 0.9f), color.copy(alpha = 0.25f), color.copy(alpha = 0f)),
                    center = Offset(cx, cy),
                    radius = glowRadius,
                ),
                radius = glowRadius,
                center = Offset(cx, cy),
            )

            drawCircle(
                color = color.copy(alpha = 0.92f),
                radius = base * (0.32f + level * 0.12f),
                center = Offset(cx, cy),
            )
        }
    }
}
