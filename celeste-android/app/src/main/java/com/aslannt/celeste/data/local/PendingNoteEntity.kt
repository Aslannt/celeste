package com.aslannt.celeste.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_notes")
data class PendingNoteEntity(
    @PrimaryKey val localId: String,
    val title: String,
    val content: String,
    val createdAt: String,
)
