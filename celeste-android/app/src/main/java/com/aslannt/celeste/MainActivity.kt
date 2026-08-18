package com.aslannt.celeste

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aslannt.celeste.data.*
import com.aslannt.celeste.ui.theme.CelesteTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CelesteTheme { CelesteScreen() }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CelesteScreen() {
    val context = LocalContext.current
    val store = remember { ConfigStore(context) }
    var config by remember { mutableStateOf(store.load()) }
    var statusText by remember { mutableStateOf("Sin comprobar") }
    var hostname by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf<List<Note>>(emptyList()) }
    var noteTitle by remember { mutableStateOf("") }
    var noteContent by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var showSettings by remember { mutableStateOf(config.coreBaseUrl.isBlank()) }
    val scope = rememberCoroutineScope()

    fun runIo(block: suspend () -> Unit) {
        scope.launch {
            busy = true
            try {
                block()
            } catch (e: Exception) {
                message = e.message ?: "Error desconocido"
            } finally {
                busy = false
            }
        }
    }

    fun refresh() = runIo {
        val current = store.load()
        val api = CelesteApi(current)
        val status = withContext(Dispatchers.IO) { api.getStatus() }
        val remoteNotes = withContext(Dispatchers.IO) { api.listNotes() }
        statusText = if (status.status == "online") "En linea" else status.status
        hostname = status.hostname
        notes = remoteNotes
        message = "Conectado a ${status.name} ${status.version}"
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Celeste") }) },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp)
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("PC", fontWeight = FontWeight.Bold)
                    Text("Estado: $statusText")
                    if (hostname.isNotBlank()) Text(hostname)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            enabled = !busy,
                            onClick = {
                                runIo {
                                    val c = store.load()
                                    require(c.pcMac.isNotBlank()) { "Configura la MAC del PC." }
                                    require(c.broadcastAddress.isNotBlank()) { "Configura la direccion broadcast." }
                                    withContext(Dispatchers.IO) {
                                        WakeOnLan.send(c.pcMac, c.broadcastAddress, c.wolPort)
                                    }
                                    message = "Magic Packet enviado"
                                }
                            },
                        ) { Text("Encender PC") }
                        OutlinedButton(enabled = !busy, onClick = { refresh() }) { Text("Actualizar") }
                    }
                }
            }

            OutlinedButton(onClick = { showSettings = !showSettings }) {
                Text(if (showSettings) "Ocultar configuracion" else "Configuracion")
            }

            if (showSettings) {
                SettingsCard(
                    config = config,
                    onConfigChange = { config = it },
                    onSave = {
                        store.save(config)
                        message = "Configuracion guardada"
                    },
                )
            }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Nueva nota", fontWeight = FontWeight.Bold)
                    OutlinedTextField(
                        value = noteTitle,
                        onValueChange = { noteTitle = it },
                        label = { Text("Titulo") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = noteContent,
                        onValueChange = { noteContent = it },
                        label = { Text("Que quieres recordar?") },
                        minLines = 4,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Button(
                        enabled = !busy && noteTitle.isNotBlank(),
                        onClick = {
                            runIo {
                                val api = CelesteApi(store.load())
                                withContext(Dispatchers.IO) {
                                    api.createNote(noteTitle.trim(), noteContent.trim())
                                }
                                noteTitle = ""
                                noteContent = ""
                                message = "Nota guardada en Celeste Brain"
                                notes = withContext(Dispatchers.IO) { api.listNotes() }
                            }
                        },
                    ) { Text("Guardar nota") }
                }
            }

            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (message.isNotBlank()) Text(message)

            Text("Ultimas notas", fontWeight = FontWeight.Bold)
            if (notes.isEmpty()) {
                Text("Todavia no hay notas cargadas.")
            } else {
                notes.sortedByDescending { it.updatedAt }.take(10).forEach { note ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(12.dp)) {
                            Text(note.title, fontWeight = FontWeight.SemiBold)
                            if (note.content.isNotBlank()) Text(note.content, maxLines = 3)
                        }
                    }
                }
            }
            Spacer(Modifier.height(20.dp))
        }
    }
}

@Composable
private fun SettingsCard(
    config: CelesteConfig,
    onConfigChange: (CelesteConfig) -> Unit,
    onSave: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Configuracion local", fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = config.coreBaseUrl,
                onValueChange = { onConfigChange(config.copy(coreBaseUrl = it)) },
                label = { Text("Celeste Core URL") },
                placeholder = { Text("http://192.168.x.x:8000") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = config.apiToken,
                onValueChange = { onConfigChange(config.copy(apiToken = it)) },
                label = { Text("API token") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = config.pcMac,
                onValueChange = { onConfigChange(config.copy(pcMac = it)) },
                label = { Text("MAC del PC") },
                placeholder = { Text("AA:BB:CC:DD:EE:FF") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = config.broadcastAddress,
                onValueChange = { onConfigChange(config.copy(broadcastAddress = it)) },
                label = { Text("Broadcast") },
                placeholder = { Text("192.168.x.255") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = config.wolPort.toString(),
                onValueChange = { value ->
                    value.toIntOrNull()?.let { onConfigChange(config.copy(wolPort = it)) }
                },
                label = { Text("Puerto WOL") },
                modifier = Modifier.fillMaxWidth(),
            )
            Button(onClick = onSave) { Text("Guardar configuracion") }
        }
    }
}
