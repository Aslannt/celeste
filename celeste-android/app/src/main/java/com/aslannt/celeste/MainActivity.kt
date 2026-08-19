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
import com.aslannt.celeste.data.local.PendingNoteEntity
import com.aslannt.celeste.ui.theme.CelesteTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
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
    val repository = remember {
        NoteRepository(context.applicationContext) { store.load() }
    }

    var config by remember { mutableStateOf(store.load()) }
    var statusText by remember { mutableStateOf("Sin comprobar") }
    var hostname by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf<List<Note>>(emptyList()) }
    var pendingNotes by remember { mutableStateOf<List<PendingNoteEntity>>(emptyList()) }
    var notifications by remember { mutableStateOf<List<CelesteNotification>>(emptyList()) }
    var noteTitle by remember { mutableStateOf("") }
    var noteContent by remember { mutableStateOf("") }
    var searchQuery by remember { mutableStateOf("") }
    var searchResults by remember { mutableStateOf<List<Note>>(emptyList()) }
    var searchPerformed by remember { mutableStateOf(false) }
    var assistantInput by remember { mutableStateOf("") }
    var assistantReply by remember { mutableStateOf("") }
    var assistantProvider by remember { mutableStateOf("") }
    var assistantEvents by remember { mutableStateOf<List<AssistantEvent>>(emptyList()) }
    var pendingAssistantActions by remember { mutableStateOf<List<AssistantEvent>>(emptyList()) }
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

    suspend fun loadPending() {
        pendingNotes = withContext(Dispatchers.IO) { repository.listPending() }
    }

    suspend fun loadAssistantConfirmations(api: CelesteApi) {
        pendingAssistantActions = withContext(Dispatchers.IO) {
            api.listPendingAssistantActions()
        }
    }

    suspend fun loadNotifications(api: CelesteApi) {
        notifications = withContext(Dispatchers.IO) { api.listNotifications() }
    }

    fun refresh() = runIo {
        val current = store.load()
        val api = CelesteApi(current)

        try {
            val status = withContext(Dispatchers.IO) { api.getStatus() }
            val sync = withContext(Dispatchers.IO) { repository.syncPending() }
            val remoteNotes = withContext(Dispatchers.IO) { api.listNotes() }
            val confirmations = withContext(Dispatchers.IO) { api.listPendingAssistantActions() }

            statusText = if (status.status == "online") "En linea" else status.status
            hostname = status.hostname
            notes = remoteNotes
            pendingAssistantActions = confirmations
            loadPending()
            try {
                loadNotifications(api)
            } catch (_: Exception) {
                notifications = emptyList()
            }

            message = if (sync.syncedCount > 0) {
                "Conectado a ${status.name} ${status.version}. Sincronizadas ${sync.syncedCount} nota(s)."
            } else {
                "Conectado a ${status.name} ${status.version}"
            }
        } catch (e: Exception) {
            statusText = "Fuera de linea"
            hostname = ""
            loadPending()
            message = if (pendingNotes.isNotEmpty()) {
                "Celeste Core no esta disponible. ${pendingNotes.size} nota(s) siguen guardadas en este telefono."
            } else {
                "Celeste Core no esta disponible."
            }
        }
    }

    LaunchedEffect(Unit) {
        loadPending()
        if (store.load().coreBaseUrl.isNotBlank()) {
            refresh()
        }
    }

    // Refresh the local notice feed while the app is active. Core is responsible
    // for any optional Gmail polling; Android never receives Google credentials.
    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000)
            val current = store.load()
            if (current.coreBaseUrl.isNotBlank()) {
                try {
                    val latest = withContext(Dispatchers.IO) {
                        CelesteApi(current).listNotifications()
                    }
                    notifications = latest
                } catch (_: Exception) {
                    // Notices are best-effort. Existing UI state remains visible.
                }
            }
        }
    }

    // While there are pending notes, retry periodically. The queue itself is
    // durable in Room, so closing or restarting the app never discards a note.
    LaunchedEffect(pendingNotes.size) {
        if (pendingNotes.isEmpty()) return@LaunchedEffect

        while (true) {
            delay(8_000)
            val sync = withContext(Dispatchers.IO) { repository.syncPending() }
            val remaining = withContext(Dispatchers.IO) { repository.listPending() }
            pendingNotes = remaining

            if (sync.syncedCount > 0) {
                val current = store.load()
                val api = CelesteApi(current)
                try {
                    val status = withContext(Dispatchers.IO) { api.getStatus() }
                    val remoteNotes = withContext(Dispatchers.IO) { api.listNotes() }
                    statusText = if (status.status == "online") "En linea" else status.status
                    hostname = status.hostname
                    notes = remoteNotes
                    message = if (remaining.isEmpty()) {
                        "Celeste Core volvio. Sincronizadas ${sync.syncedCount} nota(s) pendientes."
                    } else {
                        "Sincronizadas ${sync.syncedCount} nota(s). Quedan ${remaining.size} pendientes."
                    }
                } catch (_: Exception) {
                    // The queue is already safe in Room. A later retry will refresh the UI.
                }
            }

            if (remaining.isEmpty()) break
        }
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

            if (notifications.isNotEmpty()) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Avisos de Celeste", fontWeight = FontWeight.Bold)
                        Text("Novedades detectadas por Core. Nada se responde ni se envia automaticamente.")
                        notifications.take(5).forEach { notice ->
                            HorizontalDivider()
                            Text(notice.title, fontWeight = FontWeight.SemiBold)
                            Text(notice.detail)
                            Text(notice.source, style = MaterialTheme.typography.labelSmall)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                if (notice.source == "gmail" && notice.messageId != null) {
                                    OutlinedButton(
                                        enabled = !busy,
                                        onClick = {
                                            assistantInput = (
                                                "Lee el correo de Gmail con id ${notice.messageId}, " +
                                                    "resumelo y dime si parece necesitar respuesta."
                                                )
                                            runIo {
                                                val api = CelesteApi(store.load())
                                                withContext(Dispatchers.IO) {
                                                    api.markNotificationSeen(notice.id)
                                                }
                                                loadNotifications(api)
                                                message = "Consulta preparada para Celeste"
                                            }
                                        },
                                    ) { Text("Preguntar") }
                                } else {
                                    OutlinedButton(
                                        enabled = !busy,
                                        onClick = {
                                            runIo {
                                                val api = CelesteApi(store.load())
                                                withContext(Dispatchers.IO) {
                                                    api.markNotificationSeen(notice.id)
                                                }
                                                loadNotifications(api)
                                            }
                                        },
                                    ) { Text("Visto") }
                                }
                                TextButton(
                                    enabled = !busy,
                                    onClick = {
                                        runIo {
                                            val api = CelesteApi(store.load())
                                            withContext(Dispatchers.IO) {
                                                api.dismissNotification(notice.id)
                                            }
                                            loadNotifications(api)
                                            message = "Aviso descartado"
                                        }
                                    },
                                ) { Text("Descartar") }
                            }
                        }
                    }
                }
            }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Hablar con Celeste", fontWeight = FontWeight.Bold)
                    Text("Celeste usa herramientas con permisos separados. Las acciones sensibles esperan tu confirmacion.")
                    OutlinedTextField(
                        value = assistantInput,
                        onValueChange = { assistantInput = it },
                        label = { Text("Preguntale algo a Celeste") },
                        minLines = 2,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Button(
                        enabled = !busy && assistantInput.isNotBlank(),
                        onClick = {
                            val prompt = assistantInput.trim()
                            runIo {
                                val api = CelesteApi(store.load())
                                val result = withContext(Dispatchers.IO) {
                                    api.askCeleste(prompt)
                                }
                                assistantReply = result.reply
                                assistantProvider = result.provider
                                assistantEvents = result.events
                                assistantInput = ""
                                loadAssistantConfirmations(api)
                                message = "Respuesta de Celeste"

                                if (result.events.any { it.tool == "create_note" && it.status == "executed" }) {
                                    try {
                                        notes = withContext(Dispatchers.IO) { api.listNotes() }
                                    } catch (_: Exception) {
                                        // The assistant tool already confirmed the note write.
                                    }
                                }
                            }
                        },
                    ) { Text("Preguntar") }

                    if (assistantReply.isNotBlank()) {
                        HorizontalDivider()
                        Text(assistantReply)
                        if (assistantProvider.isNotBlank()) {
                            Text("Proveedor: $assistantProvider", style = MaterialTheme.typography.labelSmall)
                        }
                        if (assistantEvents.isNotEmpty()) {
                            Text(
                                "Herramientas: " + assistantEvents.joinToString {
                                    "${it.tool} (${it.risk}, ${it.status})"
                                },
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                    }

                    if (pendingAssistantActions.isNotEmpty()) {
                        HorizontalDivider()
                        Text("Requiere tu confirmacion", fontWeight = FontWeight.SemiBold)
                        pendingAssistantActions.forEach { action ->
                            val confirmationId = action.confirmationId
                            Text(action.summary ?: action.tool)
                            Text(
                                "${action.tool} · ${action.risk}",
                                style = MaterialTheme.typography.labelSmall,
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    enabled = !busy && confirmationId != null,
                                    onClick = {
                                        if (confirmationId != null) {
                                            runIo {
                                                val api = CelesteApi(store.load())
                                                val result = withContext(Dispatchers.IO) {
                                                    api.confirmAssistantAction(confirmationId)
                                                }
                                                assistantEvents = assistantEvents + result
                                                loadAssistantConfirmations(api)
                                                if (result.status == "executed") {
                                                    message = "Accion confirmada: ${result.tool}"
                                                    if (result.tool in setOf("update_note", "delete_note", "create_note")) {
                                                        notes = withContext(Dispatchers.IO) { api.listNotes() }
                                                    }
                                                } else {
                                                    message = result.summary ?: "La accion no se pudo ejecutar."
                                                }
                                            }
                                        }
                                    },
                                ) { Text("Confirmar") }
                                OutlinedButton(
                                    enabled = !busy && confirmationId != null,
                                    onClick = {
                                        if (confirmationId != null) {
                                            runIo {
                                                val api = CelesteApi(store.load())
                                                val result = withContext(Dispatchers.IO) {
                                                    api.cancelAssistantAction(confirmationId)
                                                }
                                                assistantEvents = assistantEvents + result
                                                loadAssistantConfirmations(api)
                                                message = "Accion cancelada: ${result.tool}"
                                            }
                                        }
                                    },
                                ) { Text("Cancelar") }
                            }
                        }
                    }
                }
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
                            val title = noteTitle.trim()
                            val content = noteContent.trim()
                            runIo {
                                val result = withContext(Dispatchers.IO) {
                                    repository.enqueueAndTrySync(title, content)
                                }

                                noteTitle = ""
                                noteContent = ""
                                loadPending()

                                if (result.syncedNow) {
                                    message = "Nota guardada en Celeste Brain"
                                    try {
                                        val api = CelesteApi(store.load())
                                        notes = withContext(Dispatchers.IO) { api.listNotes() }
                                    } catch (_: Exception) {
                                        // The POST was confirmed; a later refresh will update the list.
                                    }
                                } else {
                                    statusText = "Fuera de linea"
                                    hostname = ""
                                    message = "Nota guardada en este telefono. Se sincronizara cuando Celeste Core vuelva."
                                }
                            }
                        },
                    ) { Text("Guardar nota") }
                }
            }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Buscar en Celeste Brain", fontWeight = FontWeight.Bold)
                    Text("Busca por titulo, contenido o tags.")
                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = { value ->
                            searchQuery = value
                            if (value.isBlank()) {
                                searchPerformed = false
                                searchResults = emptyList()
                            }
                        },
                        label = { Text("Que quieres encontrar?") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Button(
                        enabled = !busy && searchQuery.isNotBlank(),
                        onClick = {
                            val query = searchQuery.trim()
                            runIo {
                                val api = CelesteApi(store.load())
                                searchResults = withContext(Dispatchers.IO) {
                                    api.searchNotes(query)
                                }
                                searchPerformed = true
                                message = if (searchResults.isEmpty()) {
                                    "No encontre notas para '$query'."
                                } else {
                                    "Encontradas ${searchResults.size} nota(s) para '$query'."
                                }
                            }
                        },
                    ) { Text("Buscar") }

                    if (searchPerformed) {
                        if (searchResults.isEmpty()) {
                            Text("Sin resultados.")
                        } else {
                            searchResults.take(10).forEach { note ->
                                HorizontalDivider()
                                Text(note.title, fontWeight = FontWeight.SemiBold)
                                if (note.content.isNotBlank()) Text(note.content, maxLines = 3)
                                if (note.tags.isNotEmpty()) {
                                    Text(note.tags.joinToString(" · "), style = MaterialTheme.typography.labelSmall)
                                }
                            }
                        }
                    }
                }
            }

            if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (message.isNotBlank()) Text(message)

            if (pendingNotes.isNotEmpty()) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            "Pendientes de sincronizar (${pendingNotes.size})",
                            fontWeight = FontWeight.Bold,
                        )
                        Text("Estas notas ya estan guardadas de forma local en este telefono.")
                        pendingNotes.take(5).forEach { note ->
                            HorizontalDivider()
                            Text(note.title, fontWeight = FontWeight.SemiBold)
                            if (note.content.isNotBlank()) Text(note.content, maxLines = 2)
                            Text("PENDIENTE", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }

            Text("Ultimas notas en Celeste Brain", fontWeight = FontWeight.Bold)
            if (notes.isEmpty()) {
                Text("Todavia no hay notas remotas cargadas.")
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
