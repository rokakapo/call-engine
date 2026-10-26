package com.callengine.capture;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final int REQ_AUDIO = 1;
    private static final int REQ_NOTIF = 2;
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        TextView tv = new TextView(this);
        tv.setText("CallAudioCapture: captures call audio (both directions) and streams PCM on port 19876 (loopback).");
        status = new TextView(this);
        status.setText("Status: idle");

        Button startBtn = new Button(this);
        startBtn.setText("Start capture");
        startBtn.setOnClickListener(v -> ensurePermsAndStart());

        Button stopBtn = new Button(this);
        stopBtn.setText("Stop capture");
        stopBtn.setOnClickListener(v -> {
            stopService(new Intent(this, CaptureService.class));
            status.setText("Status: stopped");
        });

        root.addView(tv);
        root.addView(startBtn);
        root.addView(stopBtn);
        root.addView(status);
        setContentView(root);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
        }
    }

    private void ensurePermsAndStart() {
        if (checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
        } else {
            startForegroundService(new Intent(this, CaptureService.class));
            status.setText("Status: running (streaming to 127.0.0.1:19876)");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == REQ_AUDIO && grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startForegroundService(new Intent(this, CaptureService.class));
            status.setText("Status: running (streaming to 127.0.0.1:19876)");
        } else if (requestCode == REQ_NOTIF) {
            // notification permission optional; continue
        }
    }
}


