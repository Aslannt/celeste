package com.aslannt.celeste.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

data class AssistantEvent(
    val tool: String,
    val risk: String,
    val status: String,
    val confirmationId: String? = null,
    val summary: String? = null,
)

data class AssistantReply(
    val reply: String,
    val provider: String,
    val events: List<AssistantEvent>,
)

data class CelesteNotification(
    val id: String,
    val source: String,
    val kind: String,
    val title: String,
    val detail: String,
    val createdAt: String,
    val seen: Boolean,
    val messageId: String? = null,
)

class CelesteApi(private val config: CelesteConfig) {

    fun getStatus(): CoreStatus {
        val json = request("/api/v1/status", "GET", authenticated = false)
        return CoreStatus(
            name = json.getString("name"),
            version = json.getString("version"),
            status = json.getString("status"),
            os = json.getString("os"),
            hostname = json.getString("hostname"),
            brainReady = json.getBoolean("brain_ready"),
            timeUtc = json.getString("time_utc"),
        )
    }

    fun listNotes(): List<Note> {
        val text = requestText("/api/v1/notes", "GET", authenticated = true)
        return parseNotes(text)
    }

    fun searchNotes(query: String, limit: Int = 20): List<Note> {
        val encoded = URLEncoder.encode(query, StandardCharsets.UTF_8.toString())
        val text = requestText(
            "/api/v1/notes/search?q=$encoded&limit=$limit",
            "GET",
            authenticated = true,
        )
        return parseNotes(text)
    }

    fun askCeleste(message: String): AssistantReply {
        val body = JSONObject().apply { put("message", message) }
        val json = request(
            "/api/v1/assistant/chat",
            "POST",
            authenticated = true,
            body = body.toString(),
            readTimeoutMs = 60_000,
        )
        val eventsJson = json.optJSONArray("events") ?: JSONArray()
        val events = (0 until eventsJson.length()).map { index ->
            parseAssistantEvent(eventsJson.getJSONObject(index))
        }
        return AssistantReply(
            reply = json.getString("reply"),
            provider = json.getString("provider"),
            events = events,
        )
    }

    fun listPendingAssistantActions(): List<AssistantEvent> {
        val text = requestText(
            "/api/v1/assistant/confirmations",
            "GET",
            authenticated = true,
        )
        val array = JSONArray(text)
        return (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            AssistantEvent(
                tool = item.getString("tool"),
                risk = "CONFIRM",
                status = "confirmation_required",
                confirmationId = item.getString("confirmation_id"),
                summary = item.optString("summary").takeIf { it.isNotBlank() },
            )
        }
    }

    fun confirmAssistantAction(confirmationId: String): AssistantEvent {
        val encoded = URLEncoder.encode(confirmationId, StandardCharsets.UTF_8.toString())
        val json = request(
            "/api/v1/assistant/confirm/$encoded",
            "POST",
            authenticated = true,
            readTimeoutMs = 60_000,
        )
        return parseAssistantEvent(json)
    }

    fun cancelAssistantAction(confirmationId: String): AssistantEvent {
        val encoded = URLEncoder.encode(confirmationId, StandardCharsets.UTF_8.toString())
        val json = request(
            "/api/v1/assistant/confirm/$encoded",
            "DELETE",
            authenticated = true,
        )
        return parseAssistantEvent(json)
    }

    fun listNotifications(limit: Int = 20): List<CelesteNotification> {
        val text = requestText(
            "/api/v1/notifications?limit=$limit",
            "GET",
            authenticated = true,
        )
        val array = JSONArray(text)
        return (0 until array.length()).map { index ->
            parseNotification(array.getJSONObject(index))
        }
    }

    fun markNotificationSeen(notificationId: String) {
        val encoded = URLEncoder.encode(notificationId, StandardCharsets.UTF_8.toString())
        request(
            "/api/v1/notifications/$encoded/seen",
            "POST",
            authenticated = true,
        )
    }

    fun dismissNotification(notificationId: String) {
        val encoded = URLEncoder.encode(notificationId, StandardCharsets.UTF_8.toString())
        request(
            "/api/v1/notifications/$encoded",
            "DELETE",
            authenticated = true,
        )
    }

    fun createNote(
        title: String,
        content: String,
        tags: List<String> = listOf("android"),
        idempotencyKey: String? = null,
    ): Note {
        val body = JSONObject().apply {
            put("title", title)
            put("content", content)
            put("type", "note")
            put("tags", JSONArray(tags))
        }
        val json = request(
            "/api/v1/notes",
            "POST",
            authenticated = true,
            body = body.toString(),
            idempotencyKey = idempotencyKey,
        )
        return parseNote(json)
    }

    private fun request(
        path: String,
        method: String,
        authenticated: Boolean,
        body: String? = null,
        idempotencyKey: String? = null,
        readTimeoutMs: Int = 5_000,
    ): JSONObject = JSONObject(
        requestText(path, method, authenticated, body, idempotencyKey, readTimeoutMs),
    )

    private fun requestText(
        path: String,
        method: String,
        authenticated: Boolean,
        body: String? = null,
        idempotencyKey: String? = null,
        readTimeoutMs: Int = 5_000,
    ): String {
        require(config.coreBaseUrl.isNotBlank()) { "Configura la URL de Celeste Core." }
        val connection = URL(config.coreBaseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 2500
        connection.readTimeout = readTimeoutMs
        connection.setRequestProperty("Accept", "application/json")
        if (authenticated) connection.setRequestProperty("X-Celeste-Token", config.apiToken)
        if (!idempotencyKey.isNullOrBlank()) {
            connection.setRequestProperty("X-Celeste-Idempotency-Key", idempotencyKey)
        }

        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        }

        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.use { input ->
            BufferedReader(InputStreamReader(input)).use { reader -> reader.readText() }
        }.orEmpty()

        connection.disconnect()
        if (status !in 200..299) {
            throw IllegalStateException("Celeste Core respondio HTTP $status: $text")
        }
        return text
    }

    private fun parseAssistantEvent(json: JSONObject): AssistantEvent {
        val confirmationId = if (json.isNull("confirmation_id")) {
            null
        } else {
            json.optString("confirmation_id").takeIf { it.isNotBlank() }
        }
        val summary = if (json.isNull("summary")) {
            null
        } else {
            json.optString("summary").takeIf { it.isNotBlank() }
        }
        return AssistantEvent(
            tool = json.getString("tool"),
            risk = json.getString("risk"),
            status = json.getString("status"),
            confirmationId = confirmationId,
            summary = summary,
        )
    }

    private fun parseNotification(json: JSONObject): CelesteNotification {
        val metadata = json.optJSONObject("metadata") ?: JSONObject()
        return CelesteNotification(
            id = json.getString("id"),
            source = json.getString("source"),
            kind = json.getString("kind"),
            title = json.getString("title"),
            detail = json.getString("detail"),
            createdAt = json.getString("created_at"),
            seen = json.optBoolean("seen", false),
            messageId = metadata.optString("message_id").takeIf { it.isNotBlank() },
        )
    }

    private fun parseNotes(text: String): List<Note> {
        val array = JSONArray(text)
        return (0 until array.length()).map { index -> parseNote(array.getJSONObject(index)) }
    }

    private fun parseNote(json: JSONObject): Note {
        val tagsJson = json.optJSONArray("tags") ?: JSONArray()
        val tags = (0 until tagsJson.length()).map { tagsJson.getString(it) }
        return Note(
            id = json.getString("id"),
            title = json.getString("title"),
            content = json.optString("content"),
            type = json.getString("type"),
            tags = tags,
            createdAt = json.getString("created_at"),
            updatedAt = json.getString("updated_at"),
            version = json.getInt("version"),
            deleted = json.optBoolean("deleted", false),
        )
    }
}
