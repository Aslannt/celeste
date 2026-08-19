package com.aslannt.celeste.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun CelesteBackdrop(content: @Composable () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        colors.background,
                        colors.background,
                        colors.surfaceVariant.copy(alpha = 0.42f),
                    )
                )
            )
    ) { content() }
}

@Composable
fun CelesteHero(
    statusText: String,
    hostname: String,
    pendingCount: Int,
    notificationCount: Int,
    agendaCount: Int = 0,
) {
    val colors = MaterialTheme.colorScheme
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = Color.Transparent,
            contentColor = colors.onSurface,
        ),
        border = BorderStroke(1.dp, colors.outlineVariant.copy(alpha = 0.85f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(
            modifier = Modifier
                .background(
                    Brush.linearGradient(
                        colors = listOf(
                            colors.primaryContainer.copy(alpha = 0.92f),
                            colors.secondaryContainer.copy(alpha = 0.72f),
                            colors.surface.copy(alpha = 0.92f),
                        )
                    )
                )
                .padding(horizontal = 22.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("PERSONAL AI", style = MaterialTheme.typography.labelMedium, color = colors.primary)
            Text("Celeste", style = MaterialTheme.typography.displaySmall, color = colors.onSurface)
            Text(
                "Tu memoria, agenda, inbox y automatizaciones en un solo lugar.",
                style = MaterialTheme.typography.bodyLarge,
                color = colors.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusPill(statusText, statusText.equals("En linea", ignoreCase = true))
                if (hostname.isNotBlank()) StatusPill(hostname, false)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MiniMetric("Agenda", agendaCount.toString())
                MiniMetric("Avisos", notificationCount.toString())
                MiniMetric("Pend.", pendingCount.toString())
            }
        }
    }
}

@Composable
fun CelesteCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier = modifier,
        shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
            contentColor = MaterialTheme.colorScheme.onSurface,
        ),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.72f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) { content() }
}

@Composable
fun SectionHeading(
    title: String,
    subtitle: String? = null,
    trailing: (@Composable RowScope.() -> Unit)? = null,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
            )
            if (trailing != null) Row(content = trailing)
        }
        if (!subtitle.isNullOrBlank()) {
            Text(
                subtitle,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun StatusPill(text: String, active: Boolean) {
    val colors = MaterialTheme.colorScheme
    val container = if (active) colors.tertiary.copy(alpha = 0.16f) else colors.surfaceVariant
    val content = if (active) colors.tertiary else colors.onSurfaceVariant
    Surface(
        shape = CircleShape,
        color = container,
        contentColor = content,
        border = BorderStroke(1.dp, content.copy(alpha = 0.28f)),
    ) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(content))
            Text(text, style = MaterialTheme.typography.labelMedium, color = content, maxLines = 1)
        }
    }
}

@Composable
private fun MiniMetric(label: String, value: String) {
    Surface(
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.58f),
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 9.dp)) {
            Text(
                value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
