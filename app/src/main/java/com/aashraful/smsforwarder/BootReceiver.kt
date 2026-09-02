package com.aashraful.smsforwarder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        try {
            ContextCompat.startForegroundService(
                context,
                Intent(context, ForegroundService::class.java)
            )
        } catch (e: Exception) {
            Log.e("BootReceiver", "Unable to start foreground service", e)
        }
    }
}
