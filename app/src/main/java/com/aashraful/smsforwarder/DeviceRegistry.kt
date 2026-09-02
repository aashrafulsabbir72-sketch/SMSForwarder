package com.aashraful.smsforwarder
import android.content.Context

object DeviceRegistry {
    private const val SP = "device_registry"
    private const val KEY = "known_names"

    fun add(ctx: Context, name: String) {
        val p = ctx.getSharedPreferences(SP, Context.MODE_PRIVATE)
        val set = (p.getStringSet(KEY, emptySet()) ?: emptySet()).toMutableSet()
        if (set.add(name)) p.edit().putStringSet(KEY, set).apply()
    }

    fun all(ctx: Context, self: String): List<String> {
        val p = ctx.getSharedPreferences(SP, Context.MODE_PRIVATE)
        val set = (p.getStringSet(KEY, emptySet()) ?: emptySet()).toMutableSet()
        set.add(self)
        return set.sorted()
    }
}
