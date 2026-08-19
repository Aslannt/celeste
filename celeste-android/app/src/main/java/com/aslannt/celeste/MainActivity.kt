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
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.aslannt.celeste.data.*
import com.aslannt.celeste.data.local.PendingNoteEntity
import com.aslannt.celeste.ui.AssistantResponseCard
import com.aslannt.celeste.ui.CelesteBackdrop
import com.aslannt.celeste.ui.CelesteCard
import com.aslannt.celeste.ui.CelesteHero
import com.aslannt.celeste.ui.SectionHeading
import com.aslannt.celeste.ui.theme.CelesteTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { CelesteTheme { CelesteScreen() } }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CelesteScreen() {
    val context = LocalContext.current
    val store = remember { ConfigStore(context) }
    val repository = remember { NoteRepository(context.applicationContext) { store.load() } }

    var config by remember { mutableStateOf(store.load()) }
    var statusText by remember { mutableStateOf("Sin comprobar") }
    var hostname by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf<List<Note>>(emptyList()) }
    var pendingNotes by remember { mutableStateOf<List<PendingNoteEntity>>(emptyList()) }
    var notifications by remember { mutableStateOf<List<CelesteNotification>>(emptyList()) }
    var reminders by remember { mutableStateOf<List<Reminder>>(emptyList()) }
    var calendarEvents by remember { mutableStateOf<List<CalendarEvent>>(emptyList()) }
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
            try { block() } catch (e: Exception) {
                message = e.message ?: "Error desconocido"
            } finally { busy = false }
        }
    }

    suspend fun loadPending() {
        pendingNotes = withContext(Dispatchers.IO) { repository.listPending() }
    }

    suspend fun loadAssistantConfirmations(api: CelesteApi) {
        pendingAssistantActions = withContext(Dispatchers.IO) { api.listPendingAssistantActions() }
    }

    suspend fun loadNotifications(api: CelesteApi) {
        notifications = withContext(Dispatchers.IO) { api.listNotifications() }
    }

    suspend fun loadDailyContext(api: CelesteApi) {
        reminders = try {
            withContext(Dispatchers.IO) { api.listReminders(limit = 20) }
        } catch (_: Exception) { emptyList() }
        calendarEvents = try {
            withContext(Dispatchers.IO) { api.listCalendarEvents(limit = 10) }
        } catch (_: Exception) { emptyList() }
    }

    fun refresh() = runIo {
        val current = store.load()
        val api = CelesteApi(current)
        try {
            val status = withContext(Dispatchers.IO) { api.getStatus() }
            val sync = withContext(Dispatchers.IO) { repository.syncPending() }
            notes = withContext(Dispatchers.IO) { api.listNotes() }
            pendingAssistantActions = withContext(Dispatchers.IO) { api.listPendingAssistantActions() }
            statusText = if (status.status == "online") "En linea" else status.status
            hostname = status.hostname
            loadPending()
            try { loadNotifications(api) } catch (_: Exception) { notifications = emptyList() }
            loadDailyContext(api)
            message = if (sync.syncedCount > 0) {
                "Conectado a ${status.name} ${status.version}. Sincronizadas ${sync.syncedCount} nota(s)."
            } else "Conectado a ${status.name} ${status.version}"
        } catch (e: Exception) {
            statusText = "Fuera de linea"
            hostname = ""
            loadPending()
            message = if (pendingNotes.isNotEmpty()) {
                "Celeste Core no esta disponible. ${pendingNotes.size} nota(s) siguen guardadas en este telefono."
            } else "Celeste Core no esta disponible."
        }
    }

    LaunchedEffect(Unit) {
        loadPending()
        if (store.load().coreBaseUrl.isNotBlank()) refresh()
    }

    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000)
            val current = store.load()
            if (current.coreBaseUrl.isNotBlank()) {
                try {
                    val api = CelesteApi(current)
                    notifications = withContext(Dispatchers.IO) { api.listNotifications() }
                    loadDailyContext(api)
                } catch (_: Exception) { }
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
                val api = CelesteApi(store.load())
                try {
                    val status = withContext(Dispatchers.IO) { api.getStatus() }
                    notes = withContext(Dispatchers.IO) { api.listNotes() }
                    statusText = if (status.status == "online") "En linea" else status.status
                    hostname = status.hostname
                    message = if (remaining.isEmpty()) {
                        "Celeste Core volvio. Sincronizadas ${sync.syncedCount} nota(s) pendientes."
                    } else "Sincronizadas ${sync.syncedCount} nota(s). Quedan ${remaining.size} pendientes."
                } catch (_: Exception) { }
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
                            Text("CELESTE", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                            Text(
                                "Daily intelligence",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background.copy(alpha = 0.86f)
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
                    agendaCount = reminders.size + calendarEvents.size,
                )

                if (busy) LinearProgressIndicator(Modifier.fillMaxWidth())

                if (message.isNotBlank()) {
                    Surface(
                        Modifier.fillMaxWidth(),
                        shape = MaterialTheme.shapes.medium,
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                    ) {
                        Text(message, Modifier.padding(horizontal = 14.dp, vertical = 11.dp))
                    }
                }

                DailyAgendaCard(
                    reminders = reminders,
                    events = calendarEvents,
                    busy = busy,
                    onAskReminder = { assistantInput = "Recuérdame " },
                    onAskCalendar = { assistantInput = "¿Qué tengo en el calendario " },
                    onCompleteReminder = { reminder ->
                        runIo {
                            val api = CelesteApi(store.load())
                            withContext(Dispatchers.IO) { api.completeReminder(reminder.id) }
                            loadDailyContext(api)
                            loadNotifications(api)
                            message = "Recordatorio completado"
                        }
                    },
                )

                if (showSettings && config.coreBaseUrl.isBlank()) {
                    SettingsCard(config, { config = it }) {
                        store.save(config)
                        message = "Configuracion guardada"
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionHeading(
                            "Hablar con Celeste",
                            "Pregunta por agenda, Gmail o Brain; crea recordatorios y usa herramientas controladas.",
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            AssistChip(onClick = { assistantInput = "Recuérdame mañana a las 8 " }, label = { Text("Recordatorio") })
                            AssistChip(onClick = { assistantInput = "¿Qué tengo hoy en el calendario?" }, label = { Text("Agenda") })
                        }
                        OutlinedTextField(
                            value = assistantInput,
                            onValueChange = { assistantInput = it },
                            placeholder = { Text("¿Qué necesitas?") },
                            minLines = 1,
                            maxLines = 4,
                            modifier = Modifier.fillMaxWidth(),
                            shape = MaterialTheme.shapes.medium,
                        )
                        Button(
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !busy && assistantInput.isNotBlank(),
                            onClick = {
                                val prompt = assistantInput.trim()
                                message = ""
                                runIo {
                                    val api = CelesteApi(store.load())
                                    val result = withContext(Dispatchers.IO) { api.askCeleste(prompt) }
                                    assistantReply = result.reply
                                    assistantProvider = result.provider
                                    assistantEvents = result.events
                                    assistantInput = ""
                                    loadAssistantConfirmations(api)
                                    loadDailyContext(api)
                                    loadNotifications(api)
                                    if (result.events.any { it.tool == "create_note" && it.status == "executed" }) {
                                        try { notes = withContext(Dispatchers.IO) { api.listNotes() } } catch (_: Exception) { }
                                    }
                                }
                            },
                        ) { Text("Enviar a Celeste") }

                        if (assistantReply.isNotBlank()) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                            AssistantResponseCard(
                                reply = assistantReply,
                                provider = assistantProvider,
                                events = assistantEvents,
                            )
                        }

                        if (pendingAssistantActions.isNotEmpty()) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                            Text("Requiere tu confirmacion", style = MaterialTheme.typography.titleMedium)
                            pendingAssistantActions.forEach { action ->
                                val confirmationId = action.confirmationId
                                Surface(
                                    Modifier.fillMaxWidth(),
                                    shape = MaterialTheme.shapes.medium,
                                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.48f),
                                ) {
                                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Text(action.summary ?: action.tool)
                                        Text(
                                            "${action.tool} · ${action.risk}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            Button(enabled = !busy && confirmationId != null, onClick = {
                                                if (confirmationId != null) runIo {
                                                    val api = CelesteApi(store.load())
                                                    val result = withContext(Dispatchers.IO) { api.confirmAssistantAction(confirmationId) }
                                                    assistantEvents = assistantEvents + result
                                                    loadAssistantConfirmations(api)
                                                    loadDailyContext(api)
                                                    if (result.status == "executed") {
                                                        message = "Accion confirmada: ${result.tool}"
                                                        if (result.tool in setOf("update_note", "delete_note", "create_note")) {
                                                            notes = withContext(Dispatchers.IO) { api.listNotes() }
                                                        }
                                                    } else message = result.summary ?: "La accion no se pudo ejecutar."
                                                }
                                            }) { Text("Confirmar") }
                                            OutlinedButton(enabled = !busy && confirmationId != null, onClick = {
                                                if (confirmationId != null) runIo {
                                                    val api = CelesteApi(store.load())
                                                    val result = withContext(Dispatchers.IO) { api.cancelAssistantAction(confirmationId) }
                                                    assistantEvents = assistantEvents + result
                                                    loadAssistantConfirmations(api)
                                                    message = "Accion cancelada: ${result.tool}"
                                                }
                                            }) { Text("Cancelar") }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                if (notifications.isNotEmpty()) {
                    CelesteCard(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            SectionHeading(
                                "Inbox de Celeste",
                                "Correos, recordatorios y novedades detectados por Core.",
                            )
                            notifications.take(6).forEach { notice ->
                                Surface(
                                    Modifier.fillMaxWidth(),
                                    shape = MaterialTheme.shapes.medium,
                                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                                ) {
                                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                        Text(notice.title, style = MaterialTheme.typography.titleMedium)
                                        Text(notice.detail, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        Text(
                                            notice.source.uppercase(),
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.primary,
                                        )
                                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                            if (notice.source == "gmail" && notice.messageId != null) {
                                                OutlinedButton(enabled = !busy, onClick = {
                                                    assistantInput = "Lee el correo de Gmail con id ${notice.messageId}, resumelo y dime si parece necesitar respuesta."
                                                    runIo {
                                                        val api = CelesteApi(store.load())
                                                        withContext(Dispatchers.IO) { api.markNotificationSeen(notice.id) }
                                                        loadNotifications(api)
                                                        message = "Consulta preparada para Celeste"
                                                    }
                                                }) { Text("Preguntar") }
                                            } else {
                                                OutlinedButton(enabled = !busy, onClick = {
                                                    runIo {
                                                        val api = CelesteApi(store.load())
                                                        withContext(Dispatchers.IO) { api.markNotificationSeen(notice.id) }
                                                        loadNotifications(api)
                                                    }
                                                }) { Text("Visto") }
                                            }
                                            TextButton(enabled = !busy, onClick = {
                                                runIo {
                                                    val api = CelesteApi(store.load())
                                                    withContext(Dispatchers.IO) { api.dismissNotification(notice.id) }
                                                    loadNotifications(api)
                                                }
                                            }) { Text("Descartar") }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionHeading(
                            "Captura rapida",
                            "Guarda primero en el telefono y sincroniza con Brain cuando Core este disponible.",
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
                                    val result = withContext(Dispatchers.IO) { repository.enqueueAndTrySync(title, content) }
                                    noteTitle = ""
                                    noteContent = ""
                                    loadPending()
                                    if (result.syncedNow) {
                                        message = "Nota guardada en Celeste Brain"
                                        try { notes = withContext(Dispatchers.IO) { CelesteApi(store.load()).listNotes() } } catch (_: Exception) { }
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
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionHeading("Explorar Brain", "Busca por titulo, contenido o etiquetas.")
                        OutlinedTextField(
                            value = searchQuery,
                            onValueChange = { value ->
                                searchQuery = value
                                if (value.isBlank()) { searchPerformed = false; searchResults = emptyList() }
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
                                    searchResults = withContext(Dispatchers.IO) { CelesteApi(store.load()).searchNotes(query) }
                                    searchPerformed = true
                                    message = if (searchResults.isEmpty()) "No encontre notas para '$query'." else "Encontradas ${searchResults.size} nota(s) para '$query'."
                                }
                            },
                        ) { Text("Buscar en Brain") }
                        if (searchPerformed) {
                            if (searchResults.isEmpty()) Text("Sin resultados.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            else searchResults.take(10).forEach { NotePreview(it) }
                        }
                    }
                }

                if (pendingNotes.isNotEmpty()) {
                    CelesteCard(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            SectionHeading(
                                "Offline seguro",
                                "${pendingNotes.size} nota(s) guardadas localmente esperando sincronizacion.",
                            )
                            pendingNotes.take(5).forEach { note ->
                                Surface(
                                    Modifier.fillMaxWidth(),
                                    shape = MaterialTheme.shapes.medium,
                                    color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.4f),
                                ) {
                                    Column(Modifier.padding(12.dp)) {
                                        Text(note.title, fontWeight = FontWeight.SemiBold)
                                        if (note.content.isNotBlank()) Text(note.content, maxLines = 2)
                                    }
                                }
                            }
                        }
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionHeading("Core & dispositivo", "Control local del PC y conexion con Celeste Core.")
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Button(enabled = !busy, onClick = {
                                runIo {
                                    val c = store.load()
                                    require(c.pcMac.isNotBlank()) { "Configura la MAC del PC." }
                                    require(c.broadcastAddress.isNotBlank()) { "Configura la direccion broadcast." }
                                    withContext(Dispatchers.IO) { WakeOnLan.send(c.pcMac, c.broadcastAddress, c.wolPort) }
                                    message = "Magic Packet enviado"
                                }
                            }) { Text("Encender PC") }
                            OutlinedButton(enabled = !busy, onClick = { refresh() }) { Text("Actualizar") }
                        }
                        TextButton(onClick = { showSettings = !showSettings }) {
                            Text(if (showSettings) "Ocultar configuracion" else "Configuracion local")
                        }
                    }
                }

                if (showSettings && config.coreBaseUrl.isNotBlank()) {
                    SettingsCard(config, { config = it }) {
                        store.save(config)
                        message = "Configuracion guardada"
                    }
                }

                CelesteCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        SectionHeading("Memoria reciente", "Ultimas notas sincronizadas con Celeste Brain.")
                        if (notes.isEmpty()) Text("Todavia no hay notas remotas cargadas.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        else notes.sortedByDescending { it.updatedAt }.take(10).forEach { NotePreview(it) }
                    }
                }

                Spacer(Modifier.height(28.dp))
            }
        }
    }
}

@Composable
private fun DailyAgendaCard(
    reminders: List<Reminder>,
    events: List<CalendarEvent>,
    busy: Boolean,
    onAskReminder: () -> Unit,
    onAskCalendar: () -> Unit,
    onCompleteReminder: (Reminder) -> Unit,
) {
    val uriHandler = LocalUriHandler.current

    CelesteCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionHeading(
                "Hoy & proximos",
                "Agenda real de Calendar y recordatorios programados por Celeste.",
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(onClick = onAskReminder, label = { Text("+ Recordatorio") })
                AssistChip(onClick = onAskCalendar, label = { Text("Consultar agenda") })
            }
            if (events.isEmpty() && reminders.isEmpty()) {
                Text(
                    "No hay eventos ni recordatorios proximos.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            events.take(4).forEach { event ->
                Surface(
                    Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.medium,
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.34f),
                ) {
                    Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text(event.summary.ifBlank { "Evento" }, style = MaterialTheme.typography.titleMedium)
                        Text(
                            formatEventSchedule(event.start, event.end),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (event.location.isNotBlank()) {
                            if (event.location.isWebUrl()) {
                                TextButton(onClick = { uriHandler.openUri(event.location) }) {
                                    Text("Abrir evento")
                                }
                            } else {
                                Text(
                                    event.location,
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                    }
                }
            }
            reminders.take(5).forEach { reminder ->
                Surface(
                    Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.medium,
                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.38f),
                ) {
                    Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text(reminder.title, style = MaterialTheme.typography.titleMedium)
                        Text(
                            formatSchedule(reminder.dueAt),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (reminder.message.isNotBlank()) Text(reminder.message, style = MaterialTheme.typography.bodyMedium)
                        TextButton(enabled = !busy, onClick = { onCompleteReminder(reminder) }) { Text("Marcar hecho") }
                    }
                }
            }
        }
    }
}

private val scheduleLocale = Locale("es", "CO")
private val dayFormatter = DateTimeFormatter.ofPattern("EEE d MMM", scheduleLocale)
private val timeFormatter = DateTimeFormatter.ofPattern("HH:mm", scheduleLocale)

private fun formatEventSchedule(start: String, end: String): String {
    val startDateTime = parseDateTime(start) ?: return formatSchedule(start)
    val endDateTime = parseDateTime(end)
    val day = formatDay(startDateTime.toLocalDate())
    val startTime = startDateTime.format(timeFormatter)
    val endTime = endDateTime?.format(timeFormatter)
    return if (!endTime.isNullOrBlank()) "$day · $startTime–$endTime" else "$day · $startTime"
}

private fun formatSchedule(value: String): String {
    val dateTime = parseDateTime(value)
    if (dateTime != null) {
        return "${formatDay(dateTime.toLocalDate())} · ${dateTime.format(timeFormatter)}"
    }

    val date = runCatching { LocalDate.parse(value) }.getOrNull()
    if (date != null) return formatDay(date)

    return value
        .replace("T", " · ")
        .replace("Z", " UTC")
        .take(28)
}

private fun parseDateTime(value: String) = runCatching {
    OffsetDateTime.parse(value)
        .atZoneSameInstant(ZoneId.systemDefault())
}.getOrNull()

private fun formatDay(date: LocalDate): String {
    val today = LocalDate.now()
    return when (date) {
        today -> "Hoy"
        today.plusDays(1) -> "Mañana"
        else -> date.format(dayFormatter).replaceFirstChar { it.uppercase(scheduleLocale) }
    }
}

private fun String.isWebUrl(): Boolean = startsWith("https://", ignoreCase = true) || startsWith("http://", ignoreCase = true)

@Composable
private fun NotePreview(note: Note) {
    Surface(
        Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
    ) {
        Column(Modifier.padding(13.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(note.title, style = MaterialTheme.typography.titleMedium)
            if (note.content.isNotBlank()) {
                Text(note.content, maxLines = 3, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (note.tags.isNotEmpty()) {
                Text(note.tags.joinToString(" · "), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
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
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SectionHeading("Configuracion local", "Estos valores permanecen en el dispositivo.")
            OutlinedTextField(
                value = config.coreBaseUrl,
                onValueChange = { onConfigChange(config.copy(coreBaseUrl = it)) },
                label = { Text("Celeste Core URL") },
                placeholder = { Text("http://192.168.x.x:8000") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.apiToken,
                onValueChange = { onConfigChange(config.copy(apiToken = it)) },
                label = { Text("API token") },
                visualTransformation = PasswordVisualTransformation(),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.pcMac,
                onValueChange = { onConfigChange(config.copy(pcMac = it)) },
                label = { Text("MAC del PC") },
                placeholder = { Text("AA:BB:CC:DD:EE:FF") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.broadcastAddress,
                onValueChange = { onConfigChange(config.copy(broadcastAddress = it)) },
                label = { Text("Broadcast") },
                placeholder = { Text("192.168.x.255") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = config.wolPort.toString(),
                onValueChange = { value -> value.toIntOrNull()?.let { onConfigChange(config.copy(wolPort = it)) } },
                label = { Text("Puerto WOL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
            )
            Button(modifier = Modifier.fillMaxWidth(), onClick = onSave) { Text("Guardar configuracion") }
        }
    }
}
