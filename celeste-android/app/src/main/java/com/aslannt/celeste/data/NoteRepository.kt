package com.aslannt.celeste.data

import android.content.Context
import com.aslannt.celeste.data.local.CelesteDatabase
import com.aslannt.celeste.data.local.PendingNoteEntity
import java.time.Instant
import java.util.UUID


data class SyncResult(
    val syncedCount: Int,
    val pendingCount: Int,
    val errorMessage: String? = null,
)


data class SaveNoteResult(
    val syncedNow: Boolean,
    val syncedCount: Int,
    val pendingCount: Int,
    val errorMessage: String? = null,
)


class NoteRepository(
    context: Context,
    private val configProvider: () -> CelesteConfig,
) {
    private val pendingDao = CelesteDatabase.getInstance(context).pendingNoteDao()

    suspend fun listPending(): List<PendingNoteEntity> = pendingDao.listNewestFirst()

    suspend fun enqueueAndTrySync(title: String, content: String): SaveNoteResult {
        pendingDao.insert(
            PendingNoteEntity(
                localId = UUID.randomUUID().toString(),
                title = title,
                content = content,
                createdAt = Instant.now().toString(),
            ),
        )

        val sync = syncPending()
        return SaveNoteResult(
            syncedNow = sync.errorMessage == null && sync.pendingCount == 0,
            syncedCount = sync.syncedCount,
            pendingCount = sync.pendingCount,
            errorMessage = sync.errorMessage,
        )
    }

    suspend fun syncPending(): SyncResult {
        val pending = pendingDao.listOldestFirst()
        if (pending.isEmpty()) {
            return SyncResult(syncedCount = 0, pendingCount = 0)
        }

        val api = CelesteApi(configProvider())
        try {
            api.getStatus()
        } catch (e: Exception) {
            return SyncResult(
                syncedCount = 0,
                pendingCount = pending.size,
                errorMessage = e.message ?: "Celeste Core no esta disponible",
            )
        }

        var synced = 0
        for (note in pending) {
            try {
                api.createNote(
                    title = note.title,
                    content = note.content,
                    idempotencyKey = note.localId,
                )
                pendingDao.deleteById(note.localId)
                synced += 1
            } catch (e: Exception) {
                return SyncResult(
                    syncedCount = synced,
                    pendingCount = pendingDao.count(),
                    errorMessage = e.message ?: "No se pudo sincronizar la nota",
                )
            }
        }

        return SyncResult(
            syncedCount = synced,
            pendingCount = pendingDao.count(),
        )
    }
}
