package com.project1.companion

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.view.ViewGroup

class MainActivity : Activity() {
    private val smsRequest = 401
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(36, 48, 36, 36)
        }
        layout.addView(TextView(this).apply {
            text = "Project1 — ربط الرسائل والإشعارات\n\nاختر الأذونات التي تريد تفعيلها. الرسائل الجديدة فقط هي التي تُلتقط؛ لا تتم قراءة صندوق الرسائل القديم."
            textSize = 18f
        })
        layout.addView(Button(this).apply {
            text = "تفعيل استقبال SMS"
            setOnClickListener {
                if (checkSelfPermission(Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED) {
                    status.text = "إذن SMS مفعّل. ستظهر مصادر المرسلين في واجهة Project1 بعد وصول رسالة جديدة."
                } else requestPermissions(arrayOf(Manifest.permission.RECEIVE_SMS), smsRequest)
            }
        }, matchWidth())
        layout.addView(Button(this).apply {
            text = "تفعيل الوصول لإشعارات التطبيقات"
            setOnClickListener { startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }
        }, matchWidth())
        layout.addView(Button(this).apply {
            text = "فتح دفتر الحسابات"
            setOnClickListener { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("http://127.0.0.1:8765"))) }
        }, matchWidth())
        layout.addView(status, matchWidth())
        setContentView(layout)
    }

    private val status by lazy { TextView(this).apply { text = "حالة الأذونات ستظهر هنا."; textSize = 14f } }
    private fun matchWidth() = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == smsRequest) status.text = if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) "تم منح إذن SMS. انتظر رسالة جديدة لاختبار وصول المصدر." else "لم يُمنح إذن SMS؛ لن يتم استقبال الرسائل النصية."
    }
}
