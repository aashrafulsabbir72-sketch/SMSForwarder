package com.aashraful.smsforwarder

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.BatteryManager
import android.util.Log
import androidx.core.content.ContextCompat
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.net.NetworkInterface
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

class CommandListener(private val ctx: Context) : Thread("cmd-listener") {
    @Volatile private var running = true
    private val http = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(32, TimeUnit.SECONDS)
        .writeTimeout(8, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()
    private val media = "application/json; charset=utf-8".toMediaType()
    private val prefs = ctx.getSharedPreferences(SP, Context.MODE_PRIVATE)
    private val deviceId = DeviceInfo.getDeviceId(ctx)
    private val deviceName = Config.deviceName(ctx)
    private var lastHeartbeat = 0L
    private var endpointIndex = 0
    private val endpoints: List<String>
        get() = listOf(Config.backendUrl(ctx).trim().trimEnd('/'))
            .filter { it.isNotEmpty() }

    override fun run() {
        registerWithRetry()
        var failureStreak = 0
        while (running) {
            try {
                val now = System.currentTimeMillis()
                if (now - lastHeartbeat >= Config.HEARTBEAT_MS) {
                    if (heartbeat()) lastHeartbeat = now
                }
                flushPendingAck()
                pollCommand()
                failureStreak = 0
            } catch (e: Exception) {
                failureStreak = (failureStreak + 1).coerceAtMost(6)
                Log.e("CL", "Backend error: ${e.message}")
            }
            val delay = if (failureStreak == 0) Config.COMMAND_IDLE_MS
                else minOf(15_000L, 1_000L shl (failureStreak - 1))
            try { sleep(delay) } catch (_: InterruptedException) { break }
        }
    }

    fun connectionTest(callback: (String) -> Unit) {
        Thread {
            val result = try {
                val h = requestWithFallback { base ->
                    val req = Request.Builder()
                        .url("$base/api/v1/health?device_id=$deviceId")
                        .header("X-Backend-Key", Config.backendKey(ctx))
                        .get()
                        .build()
                    http.newCall(req).execute().use { r ->
                        if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}")
                    }
                }
                if (h == null || !h.optBoolean("ok")) {
                    "❌ Backend unreachable"
                } else {
                    val online = h.optBoolean("device_online", false)
                    "✅ Backend reachable\nDevice: ${if (online) "ONLINE" else "OFFLINE"}\nID: $deviceId"
                }
            } catch (e: Exception) {
                "❌ Connection test failed: ${e.message ?: "unknown error"}"
            }
            callback(result)
        }.start()
    }

    fun stopListener() {
        running = false
        interrupt()
    }

    private fun registerWithRetry() {
        while (running) {
            if (postJson("/api/v1/register", devicePayload())) {
                lastHeartbeat = System.currentTimeMillis()
                return
            }
            try { sleep(1500) } catch (_: InterruptedException) { return }
        }
    }

    private fun heartbeat(): Boolean = postJson("/api/v1/heartbeat", devicePayload())

    private fun localIp(): String {
        return try {
            NetworkInterface.getNetworkInterfaces().toList()
                .flatMap { it.inetAddresses.toList() }
                .firstOrNull { !it.isLoopbackAddress && it.hostAddress?.contains(":") != true }
                ?.hostAddress ?: ""
        } catch (_: Exception) { "" }
    }

    private fun devicePayload(): JSONObject {
        val battery = (ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val o = JSONObject().apply {
            put("device_id", deviceId)
            put("device_name", deviceName)
            put("model", DeviceInfo.getModel())
            put("app_version", Config.APP_VERSION)
            put("paused", prefs.getBoolean(KP, false))
            put("sms_count", prefs.getInt(KC, 0))
            put("last_sms_time", prefs.getLong(KLAST, 0L))
            put("battery", battery)
            put("local_ip", localIp())
            put("control_chat_id", Config.fixedTelegramChatId())
        }
        return o
    }

    private fun pollCommand() {
        val result = requestWithFallback { base ->
            val req = Request.Builder()
                .url("$base/api/v1/poll?device_id=$deviceId&wait=25")
                .header("X-Backend-Key", Config.backendKey(ctx))
                .get()
                .build()
            http.newCall(req).execute().use { r ->
                if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}")
            }
        } ?: return
        if (!result.optBoolean("ok")) return
        val command = result.optJSONObject("command") ?: return
        val id = command.optString("id").trim()
        val raw = command.optString("text").trim()
        if (id.isBlank() || raw.isBlank()) return
        if (wasProcessed(id)) {
            ack(id, "")
            return
        }
        val resultText = route(raw)
        savePendingAck(id, resultText)
        if (ack(id, resultText)) {
            markProcessed(id)
            clearPendingAck()
        }
    }

    private fun flushPendingAck() {
        val id = prefs.getString(PENDING_ACK_ID, "")?.trim().orEmpty()
        if (id.isBlank()) return
        val result = prefs.getString(PENDING_ACK_RESULT, "") ?: ""
        if (ack(id, result)) {
            markProcessed(id)
            clearPendingAck()
        }
    }

    private fun savePendingAck(id: String, result: String) {
        prefs.edit()
            .putString(PENDING_ACK_ID, id)
            .putString(PENDING_ACK_RESULT, result)
            .commit()
    }

    private fun clearPendingAck() {
        prefs.edit()
            .remove(PENDING_ACK_ID)
            .remove(PENDING_ACK_RESULT)
            .commit()
    }

    private fun ack(id: String, result: String): Boolean {
        val body = JSONObject()
            .put("device_id", deviceId)
            .put("id", id)
            .put("result", result)
            .toString()
            .toRequestBody(media)
        return requestWithFallback { base ->
            val req = Request.Builder()
                .url("$base/api/v1/ack")
                .header("X-Backend-Key", Config.backendKey(ctx))
                .post(body)
                .build()
            http.newCall(req).execute().use { r ->
                if (!r.isSuccessful) return@use false
                JSONObject(r.body?.string() ?: "{}").optBoolean("ok", false)
            }
        } ?: false
    }

    private fun postJson(path: String, json: JSONObject): Boolean =
        requestWithFallback { base ->
            val req = Request.Builder()
                .url("$base$path")
                .header("X-Backend-Key", Config.backendKey(ctx))
                .post(json.toString().toRequestBody(media))
                .build()
            http.newCall(req).execute().use { it.isSuccessful }
        } ?: false

    private fun <T> requestWithFallback(block: (String) -> T?): T? {
        val list = endpoints
        if (list.isEmpty()) return null
        for (i in list.indices) {
            val idx = (endpointIndex + i) % list.size
            try {
                val r = block(list[idx])
                if (r != null) {
                    endpointIndex = idx
                    return r
                }
            } catch (e: Exception) {
                Log.w("CL", "${list[idx]}: ${e.message}")
            }
        }
        return null
    }

    private fun route(raw: String): String {
        return when (raw) {
            "Resume" -> {
                val ok = prefs.edit().putBoolean(KP, false).commit()
                if (ok) "▶️ Resume executed — $deviceName\n" + statusText() else "❌ Resume failed to persist — $deviceName"
            }
            "Pause" -> {
                val ok = prefs.edit().putBoolean(KP, true).commit()
                if (ok) "⏸ Pause executed — $deviceName\n" + statusText() else "❌ Pause failed to persist — $deviceName"
            }
            "Status" -> statusText()
            "StatusInfo" -> deviceInfoText()
            "Log" -> logText()
            "Test" -> testResult()
            "Health" -> backendHealthText()
            "BackendHealth" -> backendHealthText()
            "ClearLog" -> { LogStore.clear(ctx); "🧹 Log cleared — $deviceName" }
            "ResetStats" -> {
                val ok = prefs.edit().putInt(KC, 0).putLong(KLAST, 0L).commit()
                if (ok) "🔄 Daily stats reset — $deviceName\nToday: 0 SMS" else "❌ Daily stats reset failed — $deviceName"
            }
            "RestartService" -> {
                try {
                    ctx.stopService(Intent(ctx, ForegroundService::class.java))
                    ContextCompat.startForegroundService(ctx, Intent(ctx, ForegroundService::class.java))
                    "🔄 Foreground service restarted — $deviceName"
                } catch (e: Exception) {
                    "❌ Service restart failed — ${e.message ?: "unknown error"}"
                }
            }
            "Reregister" -> {
                val ok = postJson("/api/v1/register", devicePayload())
                if (ok) "🔁 Device re-registered — $deviceName" else "❌ Re-register failed — $deviceName"
            }
            "Reload" -> {
                endpointIndex = 0
                "♻️ Connection routing reloaded — $deviceName\nNext poll will use the primary configured backend."
            }
            else -> "Unknown command: $raw"
        }
    }

    private fun testResult(): String {
        val now = SimpleDateFormat("dd-MM-yyyy HH:mm:ss", Locale.getDefault()).format(Date())
        val configured = Config.isConfigured(ctx)
        return if (configured) {
            "✅ Test command received and executed — $deviceName\n" +
                "Command path: Telegram → backend → device → ACK\n" +
                "Time: $now\n" +
                "🆔 $deviceId"
        } else {
            "❌ Test cannot complete — backend configuration is missing\n🆔 $deviceId"
        }
    }

    private fun statusText(): String {
        val paused = prefs.getBoolean(KP, false)
        val battery = (ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val count = prefs.getInt(KC, 0)
        val last = prefs.getLong(KLAST, 0L)
        val lastText = if (last > 0) {
            SimpleDateFormat("dd-MM-yyyy HH:mm:ss", Locale.getDefault()).format(Date(last))
        } else "none yet"
        return "📱 $deviceName\n${if (paused) "⏸ Paused" else "🟢 Active"} | Battery: $battery% | SMS: $count\nLast SMS: $lastText\n🆔 $deviceId"
    }

    private fun backendHealthText(): String {
        val paused = prefs.getBoolean(KP, false)
        val battery = (ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val configured = Config.isConfigured(ctx)
        if (!configured) {
            return "🩺 Health — $deviceName\n" +
                "State: ${if (paused) "⏸ Paused" else "▶️ Active"}\n" +
                "Battery: $battery%\n" +
                "Backend: ⚠️ Not configured"
        }
        val health = requestWithFallback { base ->
            val req = Request.Builder()
                .url("$base/api/v1/health?device_id=$deviceId")
                .header("X-Backend-Key", Config.backendKey(ctx))
                .get()
                .build()
            http.newCall(req).execute().use { r ->
                if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}")
            }
        }
        if (health == null || !health.optBoolean("ok")) {
            return "🩺 Health — $deviceName\n" +
                "State: ${if (paused) "⏸ Paused" else "▶️ Active"}\n" +
                "Battery: $battery%\n" +
                "Backend: ❌ Unreachable"
        }
        val online = health.optBoolean("device_online", false)
        val lastSeen = health.optDouble("device_last_seen", 0.0)
        val age = if (lastSeen > 0) (System.currentTimeMillis() / 1000.0 - lastSeen).toInt().coerceAtLeast(0) else -1
        val ageText = if (age >= 0) " (${age}s ago)" else ""
        return "🩺 Health — $deviceName\n" +
            "State: ${if (paused) "⏸ Paused" else "▶️ Active"}\n" +
            "Battery: $battery%\n" +
            "Backend: ✅ Online\n" +
            "Device heartbeat: ${if (online) "✅ Online" else "❌ Offline"}$ageText\n" +
            "Endpoint: ${Config.backendUrl(ctx)}"
    }

    private fun deviceInfoText(): String {
        val b = (ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager)
            .getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val ip = localIp().ifBlank { "Not available" }
        return "📱 $deviceName\n🆔 $deviceId\n📲 ${DeviceInfo.getModel()}\n🔋 Battery: $b%\n🌐 Local IP: $ip\n📦 App: ${Config.APP_VERSION}"
    }

    private fun logText(): String {
        val entries = LogStore.getRecent(ctx, 50)
        if (entries.isEmpty()) return "$deviceName — No SMS yet"
        val out = StringBuilder("$deviceName — Last ${entries.size} SMS:")
        for ((_, ts, body) in entries) {
            val line = "\n[$ts] $body"
            if (out.length + line.length > 3800) break
            out.append(line)
        }
        return out.toString()
    }

    private fun wasProcessed(id: String) =
        (prefs.getStringSet("processed_cmds", emptySet()) ?: emptySet()).contains(id)

    private fun markProcessed(id: String) {
        val s = (prefs.getStringSet("processed_cmds", emptySet()) ?: emptySet()).toMutableSet()
        s.add(id)
        while (s.size > 200) s.remove(s.first())
        prefs.edit().putStringSet("processed_cmds", s).apply()
    }

    companion object {
        const val SP = "sms_fw_state"
        const val KP = "paused"
        const val KC = "sms_count_today"
        const val KLAST = "last_sms_time"
        const val PENDING_ACK_ID = "pending_ack_id"
        const val PENDING_ACK_RESULT = "pending_ack_result"
    }
}
