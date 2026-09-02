package com.aashraful.smsforwarder

import android.content.Context
import java.text.SimpleDateFormat
import java.util.*

object DailySummary {
    private const val PREFS = "daily_summary_prefs"
    private const val KEY_LAST_SENT = "last_sent_date"
    private const val SUMMARY_HOUR = 23

    fun checkAndSend(context: Context) {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        if (hour < SUMMARY_HOUR) return

        val todayStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_LAST_SENT, "") == todayStr) return

        val dateDisplay = SimpleDateFormat("dd-MM-yyyy", Locale.getDefault()).format(Date())
        val count = LogStore.getEntries(context).count { it.second.startsWith(dateDisplay) }
        val total = AmountStore.getTodayTotal(context)
        val msg = "Daily Summary ($dateDisplay)\nTotal SMS forwarded: $count\nTotal amount: Tk %.2f".format(total)
        TelegramSender.sendMessage(context, msg)

        prefs.edit().putString(KEY_LAST_SENT, todayStr).apply()
    }
}
