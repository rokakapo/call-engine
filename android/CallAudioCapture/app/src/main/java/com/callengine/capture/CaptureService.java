package com.callengine.capture;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;

public class CaptureService extends Service {
    private static final String TAG = "CallAudioCapture";
    private static final int PORT = 19876;
    private static final int SAMPLE_RATE = 16000;
    private static final int CHANNELS = AudioFormat.CHANNEL_IN_MONO;
    private static final int ENCODING = AudioFormat.ENCODING_PCM_16BIT;
    private static final int FRAME_BYTES = 640; // 20 ms @ 16 kHz mono int16

    private volatile boolean running = false;
    private Thread worker;
    private AudioRecord recorder;
    private volatile long framesSent = 0;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(1, buildNotification());
        if (!running) {
            running = true;
            framesSent = 0;
            worker = new Thread(this::runLoop, "capture");
            worker.start();
        }
        return START_STICKY;
    }

    private void runLoop() {
        int minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNELS, ENCODING);
        int bufSize = Math.max(minBuf, SAMPLE_RATE * 2); // ~1s ring buffer
        int source = MediaRecorder.AudioSource.VOICE_CALL;
        try {
            recorder = new AudioRecord(source, SAMPLE_RATE, CHANNELS, ENCODING, bufSize);
            if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
                Log.w(TAG, "VOICE_CALL unavailable, falling back to VOICE_COMMUNICATION");
                recorder.release();
                recorder = new AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                        SAMPLE_RATE, CHANNELS, ENCODING, bufSize);
            }
            if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG, "AudioRecord failed to initialize with both sources");
                return;
            }
        } catch (Exception e) {
            Log.e(TAG, "AudioRecord init failed: " + e);
            return;
        }
        recorder.startRecording();
        byte[] buf = new byte[FRAME_BYTES];
        try (ServerSocket server = new ServerSocket()) {
            server.setReuseAddress(true);
            server.bind(new InetSocketAddress("127.0.0.1", PORT));
            Log.i(TAG, "listening on 127.0.0.1:" + PORT);
            while (running) {
                Socket client;
                try {
                    client = server.accept();
                } catch (IOException e) {
                    if (running) Log.w(TAG, "accept error: " + e);
                    break;
                }
                Log.i(TAG, "client connected");
                try (OutputStream out = client.getOutputStream()) {
                    while (running && !client.isClosed()) {
                        int n = recorder.read(buf, 0, buf.length);
                        if (n == AudioRecord.ERROR_INVALID_OPERATION || n == AudioRecord.ERROR_BAD_VALUE) {
                            Log.e(TAG, "recorder.read error: " + n);
                            break;
                        }
                        if (n > 0) {
                            out.write(buf, 0, n);
                            framesSent++;
                            if (framesSent % 50 == 0) {
                                Log.i(TAG, "frames sent: " + framesSent);
                            }
                        }
                    }
                } catch (IOException ignored) {
                    Log.w(TAG, "client disconnected");
                } finally {
                    try { client.close(); } catch (IOException ignored) {}
                }
            }
        } catch (IOException e) {
            Log.e(TAG, "socket error: " + e);
        } finally {
            if (recorder != null) {
                try { recorder.stop(); } catch (Exception ignored) {}
                recorder.release();
                recorder = null;
            }
        }
    }

    @Override
    public void onDestroy() {
        running = false;
        if (worker != null) {
            worker.interrupt();
            try { worker.join(2000); } catch (InterruptedException ignored) {}
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    private Notification buildNotification() {
        String ch = "cap";
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel c = new NotificationChannel(ch, "Call Audio Capture", NotificationManager.IMPORTANCE_LOW);
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) nm.createNotificationChannel(c);
        }
        Notification.Builder b = new Notification.Builder(this, ch)
                .setContentTitle("Call Audio Capture")
                .setContentText("Streaming call audio to PC (127.0.0.1:" + PORT + ")")
                .setSmallIcon(android.R.drawable.ic_btn_speak_now);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            b.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE);
        }
        return b.build();
    }
}
