package com.aslannt.celeste.wake

import android.content.Context

/** Placeholder until the Vosk wake word lands (phase C): only remembers the switch. */
object WakeWordService {
    private const val PREFS = "celeste_wake"

    fun isEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean("enabled", false)

    fun setEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("enabled", enabled).apply()
    }
}
