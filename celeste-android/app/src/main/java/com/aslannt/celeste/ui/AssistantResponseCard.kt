package com.aslannt.celeste.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aslannt.celeste.data.AssistantEvent

private val rawUrlRegex = Regex("https?://[^\\s)]+", RegexOption.IGNORE_CASE)
private val markdownLinkRegex = Regex("\\[([^]]+)]\\((https?://[^)]+)\\)", RegexOption.IGNORE_CASE)
private val emptyLinkLabelRegex = Regex(
    "(?i)^[\\-•*]?\\s*(ubicaci[oó]n(?:/enlace)?|enlace|link):\\s*$",
)

private data class DisplayReply(
    val text: String,
    val links: List<String>,
)

@Composable
fun AssistantResponseCard(
    reply: String,
    provider: String,
    events: List<AssistantEvent>,
) {
    val uriHandler = LocalUriHandler.current
    val display = remember(reply) { prepareReply(reply) }
    var showDetails by remember(reply, provider, events) { mutableStateOf(false) }
    val executedTool = events.lastOrNull { it.status == "executed" }?.tool
    val eyebrow = when (executedTool) {
        "calendar_list_events", "calendar_get_event" -> "AGENDA"
        "create_reminder", "complete_reminder" -> "RECORDATORIO"
        "gmail_search", "gmail_read_message" -> "GMAIL"
        else -> "CELESTE"
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f),
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column(
            Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                eyebrow,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.primary,
            )
            if (display.text.isNotBlank()) {
                Text(
                    display.text,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
            display.links.take(2).forEachIndexed { index, url ->
                TextButton(onClick = { uriHandler.openUri(url) }) {
                    Text(if (index == 0) "Abrir enlace" else "Abrir otro enlace")
                }
            }

            if (provider.isNotBlank() || events.isNotEmpty()) {
                TextButton(onClick = { showDetails = !showDetails }) {
                    Text(if (showDetails) "Ocultar detalles ↑" else "Detalles ↓")
                }
            }

            if (showDetails) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (provider.isNotBlank()) {
                        Text(
                            "Proveedor · $provider",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    events.forEach { event ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                event.tool,
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                event.status.toDisplayStatus(),
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun prepareReply(raw: String): DisplayReply {
    val links = linkedSetOf<String>()
    var text = markdownLinkRegex.replace(raw) { match ->
        links += match.groupValues[2].trimUrlPunctuation()
        match.groupValues[1]
    }

    rawUrlRegex.findAll(text).forEach { match ->
        links += match.value.trimUrlPunctuation()
    }
    text = rawUrlRegex.replace(text, "")

    text = text
        .replace("**", "")
        .replace("__", "")
        .replace("`", "")

    val lines = text.lines()
        .map { line ->
            line.trimEnd()
                .replace(Regex("^\\s*[-*]\\s+"), "• ")
        }
        .filterNot { line -> emptyLinkLabelRegex.matches(line.trim()) }

    text = lines.joinToString("\n")
        .replace(Regex("[ \\t]+\\n"), "\n")
        .replace(Regex("\\n{3,}"), "\n\n")
        .trim()

    return DisplayReply(text = text, links = links.filter { it.isNotBlank() })
}

private fun String.trimUrlPunctuation(): String = trimEnd('.', ',', ';', ':', '!', '?', ']', '}')

private fun String.toDisplayStatus(): String = when (this) {
    "executed" -> "ejecutado"
    "confirmation_required" -> "requiere confirmación"
    "cancelled" -> "cancelado"
    "rejected" -> "rechazado"
    else -> this
}
