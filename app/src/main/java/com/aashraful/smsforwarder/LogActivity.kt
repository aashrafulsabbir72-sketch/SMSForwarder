package com.aashraful.smsforwarder

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.widget.NestedScrollView

class LogActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_log)

        val logText = findViewById<TextView>(R.id.logText)
        val clearButton = findViewById<Button>(R.id.clearLogButton)

        renderLog(logText)

        clearButton.setOnClickListener {
            LogStore.clear(this)
            renderLog(logText)
        }
    }

    private fun renderLog(logText: TextView) {
        val entries = LogStore.getEntries(this)
        if (entries.isEmpty()) {
            logText.text = "No SMS forwarded yet."
            return
        }
        val sb = StringBuilder()
        for ((sender, time, body) in entries) {
            sb.append(time).append("  |  ").append(sender).append("\n")
            sb.append(body).append("\n")
            sb.append("\u2014\u2014\u2014\u2014\u2014\u2014\u2014\u2014\n\n")
        }
        logText.text = sb.toString()
    }
}
