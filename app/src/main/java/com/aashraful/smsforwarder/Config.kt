package com.aashraful.smsforwarder

import android.content.Context
import android.os.Build

object Config {
    // Locked at build time. No configuration screen or editable backend settings are exposed.
    const val APP_VERSION = "v12"
    const val HEARTBEAT_MS = 5_000L
    const val COMMAND_IDLE_MS = 100L

    fun deviceName(ctx: Context): String = "${Build.MANUFACTURER} ${Build.MODEL}"

    fun backendUrl(ctx: Context): String = BuildConfig.FIXED_BACKEND_URL.trim().trimEnd('/')

    fun backendKey(ctx: Context): String = BuildConfig.FIXED_BACKEND_KEY.trim()

    fun fixedTelegramChatId(): String = BuildConfig.FIXED_TELEGRAM_CHAT_ID.trim()

    fun isConfigured(ctx: Context): Boolean =
        backendUrl(ctx).isNotBlank() && backendKey(ctx).isNotBlank()
}
