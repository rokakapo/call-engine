package com.project1.companion

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class NotificationCaptureService : NotificationListenerService() {
    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val extras = sbn.notification.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty().take(300)
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty().take(3000)
        val big = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString().orEmpty().take(3000)
        if (title.isBlank() && text.isBlank() && big.isBlank()) return
        val packageName = sbn.packageName ?: return
        val label = try { packageManager.getApplicationLabel(packageManager.getApplicationInfo(packageName, 0)).toString() } catch (_: Exception) { packageName }
        Thread {
            Bridge.event(packageName, label, title, listOf(text, big).filter { it.isNotBlank() }.joinToString(" "), "notification:${sbn.key}:${sbn.postTime}", SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(Date(sbn.postTime)))
        }.start()
    }
}
