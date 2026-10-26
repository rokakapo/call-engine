package com.project1.companion

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val pending = goAsync()
        Thread {
            try {
                Telephony.Sms.Intents.getMessagesFromIntent(intent).forEachIndexed { index, sms ->
                    val address = (sms.originatingAddress ?: "unknown").take(100)
                    val sourceId = Bridge.stableId("sms.sender", address)
                    val label = "SMS: $address"
                    val body = (sms.messageBody ?: "").take(4000)
                    val key = "sms:${sms.timestampMillis}:$index:${Bridge.stableId("msg", body)}"
                    Bridge.event(sourceId, label, label, body, key, SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(Date(sms.timestampMillis)))
                }
            } finally { pending.finish() }
        }.start()
    }
}
