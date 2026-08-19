package com.aslannt.celeste.data

data class CoreStatus(
    val name: String,
    val version: String,
    val status: String,
    val os: String,
    val hostname: String,
    val brainReady: Boolean,
    val timeUtc: String,
)

data class Note(
    val id: String,
    val title: String,
    val content: String,
    val type: String,
    val tags: List<String>,
    val createdAt: String,
    val updatedAt: String,
    val version: Int,
    val deleted: Boolean,
)

data class Reminder(
    val id: String,
    val title: String,
    val message: String,
    val dueAt: String,
    val createdAt: String,
    val firedAt: String?,
    val doneAt: String?,
    val cancelledAt: String?,
)

data class CalendarEvent(
    val id: String,
    val summary: String,
    val description: String,
    val location: String,
    val status: String,
    val start: String,
    val end: String,
    val timeZone: String,
    val organizer: String,
    val attendees: List<String>,
)

data class CelesteConfig(
    val coreBaseUrl: String = "",
    val apiToken: String = "celeste-local-dev",
    val pcMac: String = "",
    val broadcastAddress: String = "",
    val wolPort: Int = 9,
)
