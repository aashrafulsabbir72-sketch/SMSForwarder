package com.aashraful.smsforwarder

import android.content.Context
import java.text.SimpleDateFormat
import java.util.*

object AmountStore {
    private const val PREFS = "sms_amount_prefs"

    fun addAmount(context: Context, amount: Double) {
        val dayKey = "day_" + SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
        val monthKey = "month_" + SimpleDateFormat("yyyy-MM", Locale.getDefault()).format(Date())
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val dayTotal = prefs.getFloat(dayKey, 0f) + amount.toFloat()
        val monthTotal = prefs.getFloat(monthKey, 0f) + amount.toFloat()
        prefs.edit().putFloat(dayKey, dayTotal).putFloat(monthKey, monthTotal).apply()
    }

    fun getTodayTotal(context: Context): Float {
        val dayKey = "day_" + SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getFloat(dayKey, 0f)
    }

    fun getMonthTotal(context: Context): Float {
        val monthKey = "month_" + SimpleDateFormat("yyyy-MM", Locale.getDefault()).format(Date())
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getFloat(monthKey, 0f)
    }
}
