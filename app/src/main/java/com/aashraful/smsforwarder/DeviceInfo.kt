package com.aashraful.smsforwarder

import android.content.Context
import android.os.Build
import java.util.UUID

object DeviceInfo {

    private const val PREF = "device_identity"
    private const val KEY_ID = "device_id"

    fun getDeviceId(ctx: Context): String {
        val p = ctx.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        var id = p.getString(KEY_ID, null)

        if (id.isNullOrBlank()) {
            id = UUID.randomUUID().toString()
                .replace("-", "")
                .take(12)
                .uppercase()

            p.edit().putString(KEY_ID, id).apply()
        }

        return id
    }

    fun getModel(): String {
        return "${Build.MANUFACTURER} ${Build.MODEL}"
    }

    fun getDeviceLabel(ctx: Context): String {
        return "${Config.deviceName(ctx)} | ID: ${getDeviceId(ctx)} | ${getModel()}"
    }
}
