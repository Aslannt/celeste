package com.aslannt.celeste.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL

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
        val array = JSONArray(text)
        return (0 until array.length()).map { index -> parseNote(array.getJSONObject(index)) }
    }

    fun createNote(title: String, content: String, tags: List<String> = listOf("android")): Note {
        val body = JSONObject().apply {
            put("title", title)
            put("content", content)
            put("type", "note")
            put("tags", JSONArray(tags))
        }
        val json = request("/api/v1/notes", "POST", authenticated = true, body = body.toString())
        return parseNote(json)
    }

    private fun request(
        path: String,
        method: String,
        authenticated: Boolean,
        body: String? = null,
    ): JSONObject = JSONObject(requestText(path, method, authenticated, body))

    private fun requestText(
        path: String,
        method: String,
        authenticated: Boolean,
        body: String? = null,
    ): String {
        require(config.coreBaseUrl.isNotBlank()) { "Configura la URL de Celeste Core." }
        val connection = URL(config.coreBaseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 2500
        connection.readTimeout = 5000
        connection.setRequestProperty("Accept", "application/json")
        if (authenticated) connection.setRequestProperty("X-Celeste-Token", config.apiToken)

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
