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
import com.aslannt.celeste.ui.CelesteBackdrop
import com.aslannt.celeste.ui.CelesteCard
import com.aslannt.celeste.ui.CelesteHero
import com.aslannt.celeste.ui.SectionHeading
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

    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000)
            val current = store.load()
            if (current.coreBaseUrl.isNotBlank()) {
                try {
                    notifications = withContext(Dispatchers.IO) {
                        CelesteApi(current).listNotifications()
                    }
                } catch (_: Exception) {
                    // Notices are best-effort. Existing state remains visible.
                }
            }
        }
    }

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
                    notes = withContext(Dispatchers.IO) { api.listNotes() }
                    statusText = if (status.status == "online") "En linea" else status.status
                    hostname = status.hostname
                    message = if (remaining.isEmpty()) {
                        "Celeste Core volvio. Sincronizadas ${sync.syncedCount} nota(s) pendientes."
                    } else {
                        "Sincronizadas ${sync.syncedCount} nota(s). Quedan ${remaining.size} pendientes."
                    }
                } catch (_: Exception) {
                    // The Room queue is durable; a later retry refreshes the UI.
                }
            }

            if (remaining.isEmpty()) break
        }
    }

    CelesteBackdrop {
        Scaffold(
            containerColor = MaterialTheme.colorScheme.background.copy(alpha = 0f),
            topBar = {
                CenterAlignedTopAppBar(
                    title = {
                        Column {
                            Text(
                                "CELESTE",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                "Local intelligence",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background.copy(alpha = 0.86f),
                    ),
                )
            },
        ) { padding ->
            Column(
                modifier = Modifier
                    .padding(padding)
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                CelesteHero(
                    statusText = statusText,
                    hostname = hostname,
                    pendingCount = pendingNotes.size + pendingAssistantActions.size,
                    notificationCount = notifications.size,
                )

                if (busy) {
                    LinearProgressIndicator(
                        modifier = Modifier.fillMaxWidth(),
                        trackColor = MaterialTheme.colorScheme.surfaceVariant,
                    )
                }

                if (message.isNotBlank()) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = MaterialTheme.shapes.medium,
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                    ) {
                        Text(
                            message,
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 11.dp),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        SectionHeading(
                            title = "Core & dispositivo",
                            subtitle = "Control local del PC y conexion con Celeste Core.",
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
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
                            OutlinedButton(enabled = !busy, onClick = { refresh() }) {
                                Text("Actualizar")
                            }
                        }
                        TextButton(onClick = { showSettings = !showSettings }) {
                            Text(if (showSettings) "Ocultar configuracion" else "Configuracion local")
                        }
                    }
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

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        SectionHeading(
                            title = "Hablar con Celeste",
                            subtitle = "Pregunta, recuerda o ejecuta herramientas con permisos controlados.",
                        )
                        OutlinedTextField(
                            value = assistantInput,
                            onValueChange = { assistantInput = it },
                            placeholder = { Text("¿Qué necesitas?") },
                            minLines = 3,
                            maxLines = 8,
                            modifier = Modifier.fillMaxWidth(),
                            shape = MaterialTheme.shapes.medium,
                        )
                        Button(
                            modifier = Modifier.fillMaxWidth(),
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
                        ) { Text("Enviar a Celeste") }

                        if (assistantReply.isNotBlank()) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                            Surface(
                                modifier = Modifier.fillMaxWidth(),
                                shape = MaterialTheme.shapes.medium,
                                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f),
                            ) {
                                Column(
                                    Modifier.padding(14.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    Text(assistantReply, style = MaterialTheme.typography.bodyLarge)
                                    if (assistantProvider.isNotBlank()) {
                                        Text(
                                            "Proveedor · $assistantProvider",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                    if (assistantEvents.isNotEmpty()) {
                                        Text(
                                            assistantEvents.joinToString("  ·  ") {
                                                "${it.tool} ${it.status}"
                                            },
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }

                        if (pendingAssistantActions.isNotEmpty()) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                            Text(
                                "Requiere tu confirmacion",
                                style = MaterialTheme.typography.titleMedium,
                            )
                            pendingAssistantActions.forEach { action ->
                                val confirmationId = action.confirmationId
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = MaterialTheme.shapes.medium,
                                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.48f),
                                ) {
                                    Column(
                                        Modifier.padding(14.dp),
                                        verticalArrangement = Arrangement.spacedBy(8.dp),
                                    ) {
                                        Text(action.summary ?: action.tool)
                                        Text(
                                            "${action.tool} · ${action.risk}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
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
                    }
                }

                if (notifications.isNotEmpty()) {
                    CelesteCard(Modifier.fillMaxWidth()) {
                        Column(
                            Modifier.padding(18.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            SectionHeading(
                                title = "Inbox de Celeste",
                                subtitle = "Novedades detectadas por Core. Nada se responde ni envia automaticamente.",
                            )
                            notifications.take(5).forEach { notice ->
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = MaterialTheme.shapes.medium,
                                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                                ) {
                                    Column(
                                        Modifier.padding(14.dp),
                                        verticalArrangement = Arrangement.spacedBy(6.dp),
                                    ) {
                                        Text(notice.title, style = MaterialTheme.typography.titleMedium)
                                        Text(
                                            notice.detail,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                        Text(
                                            notice.source.uppercase(),
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.primary,
                                        )
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
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        SectionHeading(
                            title = "Captura rapida",
                            subtitle = "Guarda primero en el telefono y sincroniza con Brain cuando Core este disponible.",
                        )
                        OutlinedTextField(
                            value = noteTitle,
                            onValueChange = { noteTitle = it },
                            label = { Text("Titulo") },
                            modifier = Modifier.fillMaxWidth(),
                            shape = MaterialTheme.shapes.medium,
                        )
                        OutlinedTextField(
                            value = noteContent,
                            onValueChange = { noteContent = it },
                            label = { Text("Que quieres recordar?") },
                            minLines = 3,
                            modifier = Modifier.fillMaxWidth(),
                            shape = MaterialTheme.shapes.medium,
                        )
                        Button(
                            modifier = Modifier.fillMaxWidth(),
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
                                            notes = withContext(Dispatchers.IO) {
                                                CelesteApi(store.load()).listNotes()
                                            }
                                        } catch (_: Exception) {
                                            // A later refresh updates the list.
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

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        SectionHeading(
                            title = "Explorar Brain",
                            subtitle = "Busca por titulo, contenido o etiquetas.",
                        )
                        OutlinedTextField(
                            value = searchQuery,
                            onValueChange = { value ->
                                searchQuery = value
                                if (value.isBlank()) {
                                    searchPerformed = false
                                    searchResults = emptyList()
                                }
                            },
                            placeholder = { Text("Moto, trabajo, pendiente...") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                            shape = MaterialTheme.shapes.medium,
                        )
                        OutlinedButton(
                            modifier = Modifier.fillMaxWidth(),
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
                        ) { Text("Buscar en Brain") }

                        if (searchPerformed) {
                            if (searchResults.isEmpty()) {
                                Text(
                                    "Sin resultados.",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            } else {
                                searchResults.take(10).forEach { note ->
                                    NotePreview(note)
                                }
                            }
                        }
                    }
                }

                if (pendingNotes.isNotEmpty()) {
                    CelesteCard(Modifier.fillMaxWidth()) {
                        Column(
                            Modifier.padding(18.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            SectionHeading(
                                title = "Offline seguro",
                                subtitle = "${pendingNotes.size} nota(s) guardadas localmente esperando sincronizacion.",
                            )
                            pendingNotes.take(5).forEach { note ->
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = MaterialTheme.shapes.medium,
                                    color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.4f),
                                ) {
                                    Column(Modifier.padding(12.dp)) {
                                        Text(note.title, fontWeight = FontWeight.SemiBold)
                                        if (note.content.isNotBlank()) {
                                            Text(note.content, maxLines = 2)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        SectionHeading(
                            title = "Memoria reciente",
                            subtitle = "Ultimas notas sincronizadas con Celeste Brain.",
                        )
                        if (notes.isEmpty()) {
                            Text(
                                "Todavia no hay notas remotas cargadas.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        } else {
                            notes.sortedByDescending { it.updatedAt }.take(10).forEach { note ->
                                NotePreview(note)
                            }
                        }
                    }
                }

                Spacer(Modifier.height(28.dp))
            }
        }
    }
}

@Composable
private fun NotePreview(note: Note) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
    ) {
        Column(
            Modifier.padding(13.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Text(note.title, style = MaterialTheme.typography.titleMedium)
            if (note.content.isNotBlank()) {
                Text(
                    note.content,
                    maxLines = 3,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (note.tags.isNotEmpty()) {
                Text(
                    note.tags.joinToString(" · "),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun SettingsCard(
    config: CelesteConfig,
    onConfigChange: (CelesteConfig) -> Unit,
    onSave: () -> Unit,
) {
    CelesteCard(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            SectionHeading(
                title = "Configuracion local",
                subtitle = "Estos valores permanecen en el dispositivo.",
            )
            OutlinedTextField(
                value = config.coreBaseUrl,
                onValueChange = { onConfigChange(config.copy(coreBaseUrl = it)) },
                label = { Text("Celeste Core URL") },
                placeholder = { Text("http://192.168.x.x:8000") },
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.apiToken,
                onValueChange = { onConfigChange(config.copy(apiToken = it)) },
                label = { Text("API token") },
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.pcMac,
                onValueChange = { onConfigChange(config.copy(pcMac = it)) },
                label = { Text("MAC del PC") },
                placeholder = { Text("AA:BB:CC:DD:EE:FF") },
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.broadcastAddress,
                onValueChange = { onConfigChange(config.copy(broadcastAddress = it)) },
                label = { Text("Broadcast") },
                placeholder = { Text("192.168.x.255") },
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.wolPort.toString(),
                onValueChange = { value ->
                    value.toIntOrNull()?.let { onConfigChange(config.copy(wolPort = it)) }
                },
                label = { Text("Puerto WOL") },
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            Button(modifier = Modifier.fillMaxWidth(), onClick = onSave) {
                Text("Guardar configuracion")
            }
        }
    }
}
