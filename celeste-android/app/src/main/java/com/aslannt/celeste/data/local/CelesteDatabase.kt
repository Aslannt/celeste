package com.aslannt.celeste.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [PendingNoteEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class CelesteDatabase : RoomDatabase() {
    abstract fun pendingNoteDao(): PendingNoteDao

    companion object {
        @Volatile
        private var instance: CelesteDatabase? = null

        fun getInstance(context: Context): CelesteDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    CelesteDatabase::class.java,
                    "celeste-local.db",
                ).build().also { instance = it }
            }
    }
}
