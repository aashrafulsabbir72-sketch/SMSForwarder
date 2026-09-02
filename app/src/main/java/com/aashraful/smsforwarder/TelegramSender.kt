package com.aashraful.smsforwarder

import android.content.Context
import android.util.Log
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

object TelegramSender {
    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(8, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val media = "application/json; charset=utf-8".toMediaType()
    private val events = Executors.newSingleThreadExecutor { r ->
        Thread(r, "sms-event-uploader").apply { isDaemon = true }
    }

    fun sendMessage(ctx: Context, text: String) {
        val safe = sanitize(text)
        if (safe.isBlank()) return
        events.execute { postEvent(ctx, "sms", safe) }
    }

    fun sendRaw(ctx: Context, text: String) {
        val safe = sanitize(text)
        if (safe.isBlank()) return
        events.execute { postEvent(ctx, "event", safe) }
    }

    fun sendRawSync(ctx: Context, text: String) {
        val safe = sanitize(text)
        if (safe.isNotBlank()) postEvent(ctx, "event", safe)
    }

    fun sendMainSync(ctx: Context, text: String) {
        val safe = sanitize(text)
        if (safe.isNotBlank()) postEvent(ctx, "test", safe)
    }

    fun sendPickerSync(ctx: Context, text: String, action: String, devices: List<String>) {
        val safe = sanitize(text)
        if (safe.isNotBlank()) postEvent(ctx, "event", safe)
    }

    fun flushQueue(ctx: Context) {
        // Command results are persisted by CommandListener and retried there.
    }

    private fun postEvent(ctx: Context, kind: String, text: String) {
        if (!Config.isConfigured(ctx) || text.isBlank()) return

        val body = JSONObject()
            .put("device_id", DeviceInfo.getDeviceId(ctx))
            .put("kind", kind)
            .put("text", text)
            .toString()
            .toRequestBody(media)

        val req = Request.Builder()
            .url("${Config.backendUrl(ctx)}/api/v1/event")
            .header("X-Backend-Key", Config.backendKey(ctx))
            .post(body)
            .build()

        try {
            client.newCall(req).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.w("TGS", "event HTTP ${response.code}")
                }
            }
        } catch (e: Exception) {
            Log.w("TGS", "event failed: ${e.message}")
        }
    }

    // Redact common authentication-code formats before any event leaves the device.
    private fun sanitize(input: String): String {
        var s = input
        s = s.replace(
            Regex("(?i)(OTP\\s*/?\\s*Code\\s*:\\s*)\\d{4,8}"),
            "$1[REDACTED]"
        )
        s = s.replace(
            Regex("(?i)(verification\\s*code\\s*[:=-]?\\s*)\\d{4,8}"),
            "$1[REDACTED]"
        )
        s = s.replace(
            Regex("(?i)(one[- ]?time\\s*(password|code)\\s*[:=-]?\\s*)\\d{4,8}"),
            "$1[REDACTED]"
        )
        return s.take(3500)
    }

    fun escapeHtml(s: String) = sanitize(s)
}
