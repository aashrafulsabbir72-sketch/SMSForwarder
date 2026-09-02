package com.aashraful.smsforwarder

import android.content.Context

object ForwardingState {
    private const val PREFS = "forwarding_state_prefs"
    private const val KEY_ENABLED = "enabled"

    fun isEnabled(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return prefs.getBoolean(KEY_ENABLED, true)
    }

    fun setEnabled(context: Context, enabled: Boolean) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs.edit().putBoolean(KEY_ENABLED, enabled).apply()
    }
}
