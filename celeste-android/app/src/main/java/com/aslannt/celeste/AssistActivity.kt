package com.aslannt.celeste

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.aslannt.celeste.ui.AssistantScreen
import com.aslannt.celeste.ui.Night
import com.aslannt.celeste.voice.AssistantSession
import com.aslannt.celeste.voice.Phase
import kotlinx.coroutines.delay

/**
 * What opens with the assistant gesture (long-press power/home), the "Celeste"
 * wake word, or a headset button: a translucent sheet with the orb that starts
 * listening right away and closes by itself a moment after she finishes.
 */
class AssistActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { AssistOverlay(onClose = { finish() }) }
    }
}

@androidx.compose.runtime.Composable
private fun AssistOverlay(onClose: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val session = remember { AssistantSession(context, scope) }
    val noRipple = remember { MutableInteractionSource() }

    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) session.listen() else onClose()
    }

    LaunchedEffect(Unit) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            session.listen()
        } else {
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }
    // Close shortly after the turn ends, unless the user taps again to keep talking.
    LaunchedEffect(session.phase) {
        if (session.phase == Phase.IDLE || session.phase == Phase.ERROR) {
            delay(if (session.phase == Phase.ERROR) 4000 else 3500)
            if (session.phase == Phase.IDLE || session.phase == Phase.ERROR) onClose()
        }
    }
    DisposableEffect(Unit) { onDispose { session.cancel() } }

    Box(
        Modifier
            .fillMaxSize()
            .clickable(interactionSource = noRipple, indication = null) { onClose() },
        contentAlignment = Alignment.BottomCenter,
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .padding(12.dp)
                .clip(RoundedCornerShape(28.dp))
                .background(Night.copy(alpha = 0.96f))
                .clickable(interactionSource = noRipple, indication = null) { /* keep open */ }
                .padding(vertical = 20.dp),
        ) {
            AssistantScreen(session = session, orbSize = 200.dp, modifier = Modifier.fillMaxWidth())
        }
    }
}
