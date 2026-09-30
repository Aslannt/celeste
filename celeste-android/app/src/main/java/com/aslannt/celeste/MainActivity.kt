package com.aslannt.celeste

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.aslannt.celeste.data.CelesteApi
import com.aslannt.celeste.data.ConfigStore
import com.aslannt.celeste.ui.AssistantScreen
import com.aslannt.celeste.ui.Night
import com.aslannt.celeste.voice.AssistantSession
import com.aslannt.celeste.wake.WakeWordService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Home: just Celeste's orb. Everything else lives behind the gear. */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = android.graphics.Color.parseColor("#0B0714")
        window.navigationBarColor = android.graphics.Color.parseColor("#0B0714")
        setContent { HomeScreen() }
    }
}

private val Lilac = Color(0xFFB8A9D9)
private val Panel = Color(0xFF160E26)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val session = remember { AssistantSession(context, scope) }
    val store = remember { ConfigStore(context) }
    var showSettings by remember { mutableStateOf(!session.isConfigured) }
    var online by remember { mutableStateOf<Boolean?>(null) }

    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) session.listen()
    }

    LaunchedEffect(showSettings) {
        if (showSettings || !session.isConfigured) return@LaunchedEffect
        online = withContext(Dispatchers.IO) { runCatching { CelesteApi(store.load()).getStatus() }.isSuccess }
    }

    Box(Modifier.fillMaxSize().background(Night)) {
        // Connection dot + gear: the only chrome on screen.
        Box(
            Modifier
                .align(Alignment.TopStart)
                .padding(start = 24.dp, top = 28.dp)
                .size(8.dp)
                .clip(CircleShape)
                .background(
                    when (online) {
                        true -> Color(0xFF86EFAC)
                        false -> Color(0xFFFDA4AF)
                        null -> Lilac.copy(alpha = 0.3f)
                    },
                ),
        )
        TextButton(
            onClick = { showSettings = true },
            modifier = Modifier.align(Alignment.TopEnd).padding(top = 8.dp, end = 8.dp),
        ) { Text("⚙", color = Lilac.copy(alpha = 0.7f), fontSize = 20.sp) }

        AssistantScreen(
            session = session,
            orbSize = 300.dp,
            modifier = Modifier.fillMaxSize().padding(bottom = 40.dp),
        )
    }

    // Tapping the orb goes through the session; ask for the mic the first time.
    LaunchedEffect(Unit) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    if (showSettings) {
        ModalBottomSheet(onDismissRequest = { showSettings = false }, containerColor = Panel) {
            SettingsSheet(onClose = { showSettings = false })
        }
    }
}

@Composable
private fun SettingsSheet(onClose: () -> Unit) {
    val context = LocalContext.current
    val store = remember { ConfigStore(context) }
    val initial = remember { store.load() }
    var url by remember { mutableStateOf(initial.coreBaseUrl) }
    var token by remember { mutableStateOf(initial.apiToken) }
    var wakeWord by remember { mutableStateOf(WakeWordService.isEnabled(context)) }
    val fieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = Color.White,
        unfocusedTextColor = Color.White,
        focusedBorderColor = Color(0xFFA78BFA),
        unfocusedBorderColor = Lilac.copy(alpha = 0.3f),
        focusedLabelColor = Color(0xFFA78BFA),
        unfocusedLabelColor = Lilac,
        cursorColor = Color(0xFFA78BFA),
    )

    Column(
        Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("Celeste", color = Color.White, fontSize = 22.sp)
        OutlinedTextField(
            value = url, onValueChange = { url = it.trim() },
            label = { Text("Dirección del Core (ej. http://100.x.x.x:8000)") },
            singleLine = true, colors = fieldColors, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = token, onValueChange = { token = it.trim() },
            label = { Text("Token") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            colors = fieldColors, modifier = Modifier.fillMaxWidth(),
        )
        SettingRow(
            title = "Decir “Celeste” para llamarla",
            subtitle = "Escucha solo esa palabra, en el teléfono. Deja una notificación fija.",
        ) {
            Switch(
                checked = wakeWord,
                onCheckedChange = {
                    wakeWord = it
                    WakeWordService.setEnabled(context, it)
                },
                colors = SwitchDefaults.colors(checkedTrackColor = Color(0xFF7C3AED)),
            )
        }
        SheetButton("Hacerla mi asistente (botón de encendido)") {
            context.startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        SheetButton("Panel completo (agenda, notas, recordatorios)") {
            context.startActivity(Intent(context, DashboardActivity::class.java))
        }
        Spacer(Modifier.height(4.dp))
        SheetButton("Guardar", primary = true) {
            store.save(initial.copy(coreBaseUrl = url, apiToken = token))
            onClose()
        }
    }
}

@Composable
private fun SettingRow(title: String, subtitle: String, trailing: @Composable () -> Unit) {
    Box(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(end = 64.dp)) {
            Text(title, color = Color.White, fontSize = 15.sp)
            Text(subtitle, color = Lilac.copy(alpha = 0.7f), fontSize = 12.sp)
        }
        Box(Modifier.align(Alignment.CenterEnd)) { trailing() }
    }
}

@Composable
private fun SheetButton(label: String, primary: Boolean = false, onClick: () -> Unit) {
    TextButton(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(if (primary) Color(0xFF6D28D9) else Color(0x1FA78BFA)),
    ) {
        Text(label, color = if (primary) Color.White else Lilac, fontSize = 14.sp)
    }
}
