package com.aslannt.celeste.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aslannt.celeste.voice.AssistantSession
import com.aslannt.celeste.voice.Phase

val Night = Color(0xFF0B0714)
private val Mist = Color(0xFFB8A9D9)
private val Soft = Color(0xFFF3E8FF)

fun hintFor(phase: Phase): String = when (phase) {
    Phase.IDLE -> "Toca para hablar"
    Phase.LISTENING -> "Te escucho…"
    Phase.THINKING -> "Pensando…"
    Phase.SPEAKING -> "Toca para callarla"
    Phase.ERROR -> "Toca para reintentar"
}

/** The whole app, basically: an orb, one line of what you said, one of what she said. */
@Composable
fun AssistantScreen(session: AssistantSession, orbSize: Dp, modifier: Modifier = Modifier) {
    val noRipple = remember { MutableInteractionSource() }
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            Modifier
                .size(orbSize)
                .clickable(interactionSource = noRipple, indication = null) { session.toggle() },
            contentAlignment = Alignment.Center,
        ) {
            NebulaOrb(session.phase, session.level, Modifier.size(orbSize))
        }
        Spacer(Modifier.height(8.dp))
        Text(
            hintFor(session.phase),
            color = Mist.copy(alpha = 0.7f),
            fontSize = 13.sp,
            letterSpacing = 1.sp,
        )
        Spacer(Modifier.height(20.dp))
        if (session.heard.isNotBlank()) {
            Text(
                "“${session.heard}”",
                color = Mist,
                fontSize = 14.sp,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 32.dp),
            )
            Spacer(Modifier.height(10.dp))
        }
        if (session.reply.isNotBlank()) {
            Text(
                session.reply,
                color = if (session.phase == Phase.ERROR) Color(0xFFFDA4AF) else Soft,
                fontSize = 17.sp,
                fontWeight = FontWeight.Light,
                lineHeight = 24.sp,
                textAlign = TextAlign.Center,
                maxLines = 8,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 28.dp),
            )
        }
    }
}
