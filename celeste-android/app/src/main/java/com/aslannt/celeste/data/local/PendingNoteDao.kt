package com.aslannt.celeste.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface PendingNoteDao {
    @Query("SELECT * FROM pending_notes ORDER BY createdAt DESC")
    suspend fun listNewestFirst(): List<PendingNoteEntity>

    @Query("SELECT * FROM pending_notes ORDER BY createdAt ASC")
    suspend fun listOldestFirst(): List<PendingNoteEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(note: PendingNoteEntity)

    @Query("DELETE FROM pending_notes WHERE localId = :localId")
    suspend fun deleteById(localId: String)

    @Query("SELECT COUNT(*) FROM pending_notes")
    suspend fun count(): Int
}
