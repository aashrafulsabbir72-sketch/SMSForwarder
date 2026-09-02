package com.aashraful.smsforwarder

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat

class ForegroundService : Service() {
    private var cmd: CommandListener? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        try {
            val notification = buildNotification()
            val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING
            } else 0
            ServiceCompat.startForeground(this, 1, notification, type)
        } catch (e: Exception) {
            stopSelf(startId)
            return START_NOT_STICKY
        }

        cmd?.stopListener()
        cmd = CommandListener(applicationContext).also { it.start() }
        return START_STICKY
    }

    override fun onDestroy() {
        cmd?.stopListener()
        cmd = null
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun buildNotification(): android.app.Notification {
        val channelId = "sms_fw"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(
                    channelId,
                    "SMS Forwarder control",
                    NotificationManager.IMPORTANCE_LOW
                )
            )
        }
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle("SMS Forwarder — ${Config.deviceName(this)}")
            .setContentText("Remote control connection active")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }
}
