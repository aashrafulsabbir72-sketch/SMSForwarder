package com.aashraful.smsforwarder
import android.content.Context
import org.json.JSONArray
object QueueStore {
    private const val P = "sms_q"; private const val K = "q"; private const val MAX = 50
    @Synchronized fun addPending(c: Context?, t: String) {
        val ctx = c?.applicationContext ?: return
        val l = list(ctx).toMutableList(); l.add(t)
        while (l.size > MAX) l.removeAt(0)
        save(ctx, l)
    }
    @Synchronized fun getPending(c: Context) = list(c)
    @Synchronized fun removeFirst(c: Context) { val l = list(c).toMutableList(); if (l.isNotEmpty()) { l.removeAt(0); save(c, l) } }
    private fun list(c: Context): List<String> {
        val arr = JSONArray(c.getSharedPreferences(P, Context.MODE_PRIVATE).getString(K, "[]") ?: "[]")
        return (0 until arr.length()).map { arr.getString(it) }
    }
    private fun save(c: Context, l: List<String>) {
        val arr = JSONArray(); l.forEach { arr.put(it) }
        c.getSharedPreferences(P, Context.MODE_PRIVATE).edit().putString(K, arr.toString()).apply()
    }
}
