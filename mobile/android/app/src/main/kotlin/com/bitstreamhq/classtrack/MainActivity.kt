package com.bitstreamhq.classtrack

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createNotificationChannels()
    }

    /**
     * The channels the backend names in each push (push_service.py), so a teacher
     * can silence class reminders and keep the alerts, or the other way round, in
     * the phone's settings. Creating one that exists changes nothing.
     */
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel("classes", "Class reminders", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Shortly before each of your classes"
            },
        )
        manager.createNotificationChannel(
            NotificationChannel("alerts", "Alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Missed classes, reschedules and other news about your classes"
            },
        )
    }
}
