package com.aashraful.smsforwarder
import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
object LogStore {
    private const val P = "sms_log"; private const val K = "entries"; private const val MAX = 500
    fun addEntry(c: Context, sender: String, time: String, body: String) {
        val pr = c.getSharedPreferences(P, Context.MODE_PRIVATE)
        val arr = JSONArray(pr.getString(K, "[]") ?: "[]")
        val na = JSONArray()
        na.put(JSONObject().apply { put("s", sender); put("t", time); put("b", body) })
        for (i in 0 until arr.length()) { if (na.length() >= MAX) break; na.put(arr.get(i)) }
        pr.edit().putString(K, na.toString()).apply()
    }
    fun getRecent(c: Context, n: Int) = getEntries(c).take(n)
    fun getEntries(c: Context): List<Triple<String, String, String>> {
        val arr = JSONArray(c.getSharedPreferences(P, Context.MODE_PRIVATE).getString(K, "[]") ?: "[]")
        return (0 until arr.length()).map {
            arr.getJSONObject(it).let { o -> Triple(o.getString("s"), o.getString("t"), o.getString("b")) }
        }
    }
    fun clear(c: Context) { c.getSharedPreferences(P, Context.MODE_PRIVATE).edit().putString(K, "[]").apply() }
}
