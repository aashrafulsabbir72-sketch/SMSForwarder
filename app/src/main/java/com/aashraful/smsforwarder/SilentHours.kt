package com.aashraful.smsforwarder

import android.content.Context
import java.util.Calendar

object SilentHours {
    private const val START_HOUR = 23
    private const val END_HOUR = 7

    fun isSilent(context: Context): Boolean {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return if (START_HOUR > END_HOUR) {
            hour >= START_HOUR || hour < END_HOUR
        } else {
            hour in START_HOUR until END_HOUR
        }
    }
}
