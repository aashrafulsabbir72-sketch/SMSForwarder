package com.aashraful.smsforwarder
import android.Manifest
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private val PERMS = arrayOf(Manifest.permission.RECEIVE_SMS, Manifest.permission.READ_SMS)
    private val REQ = 101

    private val prefListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
        if (key == CommandListener.KP || key == CommandListener.KC) {
            runOnUiThread {
                updateStatus(findViewById(R.id.statusText), findViewById(R.id.pauseButton))
                updateStats(findViewById(R.id.statsText))
            }
        }
    }

    override fun onCreate(s: Bundle?) {
        super.onCreate(s); setContentView(R.layout.activity_main)
        findViewById<TextView>(R.id.tvTitle).text = "SMS Forwarder"
        val st = findViewById<TextView>(R.id.statusText)
        val statsT = findViewById<TextView>(R.id.statsText)
        val pb = findViewById<Button>(R.id.pauseButton)
        updateStatus(st, pb); updateStats(statsT)
        startBackendServiceIfReady()
        pb.setOnClickListener {
            val pr = getSharedPreferences(CommandListener.SP, MODE_PRIVATE)
            val cur = pr.getBoolean(CommandListener.KP, false)
            pr.edit().putBoolean(CommandListener.KP, !cur).apply()
            updateStatus(st, pb)
            Toast.makeText(this, if (!cur) "Paused" else "Resumed", Toast.LENGTH_SHORT).show()
        }
        findViewById<Button>(R.id.grantButton).setOnClickListener { reqPerms() }
        findViewById<Button>(R.id.batteryButton).setOnClickListener { reqBatt() }
        findViewById<Button>(R.id.viewLogButton).setOnClickListener { startActivity(Intent(this, LogActivity::class.java)) }
        findViewById<Button>(R.id.testButton).setOnClickListener {
            val listener = CommandListener(applicationContext)
            listener.connectionTest { result ->
                runOnUiThread { Toast.makeText(this, result, Toast.LENGTH_LONG).show() }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        updateStatus(findViewById(R.id.statusText), findViewById(R.id.pauseButton))
        updateStats(findViewById(R.id.statsText))
        getSharedPreferences(CommandListener.SP, MODE_PRIVATE).registerOnSharedPreferenceChangeListener(prefListener)
    }

    override fun onPause() {
        super.onPause()
        getSharedPreferences(CommandListener.SP, MODE_PRIVATE).unregisterOnSharedPreferenceChangeListener(prefListener)
    }

    private fun updateStatus(tv: TextView, pb: Button) {
        val ok = PERMS.all { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }
        val pr = getSharedPreferences(CommandListener.SP, MODE_PRIVATE)
        val p = pr.getBoolean(CommandListener.KP, false)
        pb.text = if (p) "RESUME SMS COLLECTION" else "PAUSE SMS COLLECTION"
        pb.backgroundTintList = android.content.res.ColorStateList.valueOf(if (p) android.graphics.Color.parseColor("#E53935") else android.graphics.Color.parseColor("#00897B"))
        tv.text = if (ok) "Status: SMS permission granted ✅\nForwarding: ${if (p) "⏸ PAUSED" else "▶ Active"}" else "Status: SMS permission NOT granted ❌"
    }
    private fun updateStats(tv: TextView) {
        val c = getSharedPreferences(CommandListener.SP, MODE_PRIVATE).getInt(CommandListener.KC, 0)
        tv.text = "Today: $c SMS"
    }


    private fun hasSmsPermissions(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED &&
        ContextCompat.checkSelfPermission(this, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED

    private fun startBackendServiceIfReady() {
        // The control listener uses the remoteMessaging foreground service type and does not require
        // location permission just to stay connected to the backend.
        try {
            ContextCompat.startForegroundService(this, Intent(this, ForegroundService::class.java))
        } catch (e: SecurityException) {
            Toast.makeText(this, "Background service permission is not ready", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Toast.makeText(this, "Could not start background service", Toast.LENGTH_LONG).show()
        }
    }


    private fun reqPerms() {
        val m = PERMS.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (m.isNotEmpty()) ActivityCompat.requestPermissions(this, m.toTypedArray(), REQ)
        else Toast.makeText(this, "Already granted", Toast.LENGTH_SHORT).show()
    }
    private fun reqBatt() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName))
                startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).also { it.data = Uri.parse("package:$packageName") })
            else Toast.makeText(this, "Already optimized", Toast.LENGTH_SHORT).show()
        }
    }
    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, gr: IntArray) {
        super.onRequestPermissionsResult(rc, p, gr)
        if (rc == REQ) {
            updateStatus(findViewById(R.id.statusText), findViewById(R.id.pauseButton))
            if (hasSmsPermissions()) startBackendServiceIfReady()
        }
    }
}
