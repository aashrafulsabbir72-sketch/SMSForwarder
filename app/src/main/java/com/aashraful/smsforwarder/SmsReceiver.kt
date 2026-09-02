package com.aashraful.smsforwarder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import java.text.SimpleDateFormat
import java.util.*

class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val pr = ctx.getSharedPreferences(CommandListener.SP, Context.MODE_PRIVATE)
        if (pr.getBoolean(CommandListener.KP, false)) return

        val msgs = Telephony.Sms.Intents.getMessagesFromIntent(intent)
        if (msgs.isNullOrEmpty()) return

        val sender = msgs[0].originatingAddress ?: ""
        val sl = sender.lowercase()
        if (!sl.contains("bkash") && !sl.contains("nagad")) return

        val body = msgs.joinToString("") { it.messageBody ?: "" }
        val fp = "$sender|${msgs[0].timestampMillis}|${body.hashCode()}"
        if (DedupStore.isDuplicate(ctx, fp)) return

        DedupStore.markSeen(ctx, fp)
        val ts = SimpleDateFormat("dd-MM-yyyy HH:mm:ss", Locale.getDefault())
            .format(Date(msgs[0].timestampMillis))
        LogStore.addEntry(ctx, sender, ts, body)

        pr.edit()
            .putInt(CommandListener.KC, pr.getInt(CommandListener.KC, 0) + 1)
            .putLong(CommandListener.KLAST, msgs[0].timestampMillis)
            .apply()

        // Forward transaction SMS through the authenticated backend.
        // TelegramSender redacts common OTP/verification-code patterns.
        TelegramSender.sendMessage(ctx, body)
    }
}
