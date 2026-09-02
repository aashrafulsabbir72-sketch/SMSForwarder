package com.aashraful.smsforwarder

import android.content.Context
import org.json.JSONArray

object DedupStore {
    private const val PREFS = "sms_dedup_prefs"
    private const val KEY = "seen_fingerprints"
    private const val MAX_SEEN = 200

    @Synchronized
    fun isDuplicate(context: Context, fingerprint: String): Boolean {
        return getSeenList(context).contains(fingerprint)
    }

    @Synchronized
    fun markSeen(context: Context, fingerprint: String) {
        val list = getSeenList(context).toMutableList()
        list.add(fingerprint)
        while (list.size > MAX_SEEN) list.removeAt(0)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val array = JSONArray()
        for (item in list) array.put(item)
        prefs.edit().putString(KEY, array.toString()).apply()
    }

    private fun getSeenList(context: Context): List<String> {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val current = prefs.getString(KEY, "[]") ?: "[]"
        val array = JSONArray(current)
        val list = mutableListOf<String>()
        for (i in 0 until array.length()) list.add(array.getString(i))
        return list
    }
}
