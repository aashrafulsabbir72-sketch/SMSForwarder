package com.aashraful.smsforwarder

import android.content.Context

object BalanceStore {
    private const val PREFS = "sms_balance_prefs"

    fun setBalance(context: Context, source: String, balance: Double, time: String) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs.edit()
            .putFloat("balance_$source", balance.toFloat())
            .putString("balance_time_$source", time)
            .apply()
    }

    fun getBalance(context: Context, source: String): Pair<Float, String>? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.contains("balance_$source")) return null
        return Pair(prefs.getFloat("balance_$source", 0f), prefs.getString("balance_time_$source", "") ?: "")
    }
}
