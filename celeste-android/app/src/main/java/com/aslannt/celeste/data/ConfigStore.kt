package com.aslannt.celeste.data

import android.content.Context

class ConfigStore(context: Context) {
    private val prefs = context.getSharedPreferences("celeste_config", Context.MODE_PRIVATE)

    fun load(): CelesteConfig = CelesteConfig(
        coreBaseUrl = prefs.getString("coreBaseUrl", "") ?: "",
        apiToken = prefs.getString("apiToken", "celeste-local-dev") ?: "celeste-local-dev",
        pcMac = prefs.getString("pcMac", "") ?: "",
        broadcastAddress = prefs.getString("broadcastAddress", "") ?: "",
        wolPort = prefs.getInt("wolPort", 9),
    )

    fun save(config: CelesteConfig) {
        prefs.edit()
            .putString("coreBaseUrl", config.coreBaseUrl.trimEnd('/'))
            .putString("apiToken", config.apiToken)
            .putString("pcMac", config.pcMac)
            .putString("broadcastAddress", config.broadcastAddress)
            .putInt("wolPort", config.wolPort)
            .apply()
    }
}
