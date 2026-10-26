package com.project1.companion

import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

object Bridge {
    private const val BASE = "http://127.0.0.1:8765"

    private fun request(path: String, method: String = "GET", body: JSONObject? = null): String? {
        var connection: HttpURLConnection? = null
        return try {
            connection = (URL(BASE + path).openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = 2500
                readTimeout = 2500
                if (body != null) {
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                }
            }
            val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
            stream?.use { String(it.readBytes(), Charsets.UTF_8) }
        } catch (e: Exception) {
            Log.w("Project1Bridge", "Local backend unavailable (${e.javaClass.simpleName})")
            null
        } finally { connection?.disconnect() }
    }

    fun discovered(id: String, label: String) {
        request("/api/senders/discovered", "POST", JSONObject().put("senders", JSONArray().put(JSONObject().put("package", id).put("label", label))))
    }

    private fun isSelected(id: String): Boolean {
        val response = request("/api/senders") ?: return false
        return try {
            val senders = JSONObject(response).optJSONArray("senders") ?: return false
            (0 until senders.length()).any { i ->
                val sender = senders.getJSONObject(i)
                sender.optString("package") == id && sender.optInt("selected", 0) == 1
            }
        } catch (_: Exception) { false }
    }

    fun event(id: String, label: String, title: String, text: String, key: String, postedAt: String? = null) {
        // Discover source names, but never send notification/SMS content until the user selected it in the web UI.
        discovered(id, label)
        if (!isSelected(id)) return
        val body = JSONObject().put("package", id).put("app_label", label).put("title", title).put("text", text).put("notification_key", key)
        if (postedAt != null) body.put("posted_at", postedAt)
        request("/api/notifications", "POST", body)
    }

    fun stableId(prefix: String, value: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        val short = bytes.take(10).joinToString("") { "%02x".format(it) }
        return "$prefix.$short"
    }
}
