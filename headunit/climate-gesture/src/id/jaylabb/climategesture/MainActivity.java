package id.jaylabb.climategesture;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Start / stop the service and show its log. */
public class MainActivity extends Activity {
    private final Handler h = new Handler(Looper.getMainLooper());
    private TextView logView, status;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(48, 48, 48, 48);

        TextView title = new TextView(this);
        title.setText("Climate gesture");
        title.setTextSize(32);
        root.addView(title);

        TextView help = new TextView(this);
        help.setText("Hold two fingers still for a moment, then slide.\n"
                + "Left / right: fan 1-10.   Up / down: temperature 15.5-30.5 °C (0.5 steps).\n"
                + "Root comes from the head unit's own ADB (127.0.0.1:5555), so 'Enable ADB' must stay on.\n"
                + "Port 5555 is closed to WiFi while this runs. To update from a laptop, tap 'Open ADB 5 min' first.");
        help.setTextSize(18);
        help.setPadding(0, 16, 0, 24);
        root.addView(help);

        status = new TextView(this);
        status.setTextSize(18);
        root.addView(status);

        LinearLayout row = new LinearLayout(this);
        Button start = new Button(this);
        start.setText("Start");
        start.setOnClickListener(v -> startForegroundService(new Intent(this, GestureService.class)));
        Button stop = new Button(this);
        stop.setText("Stop");
        stop.setOnClickListener(v -> stopService(new Intent(this, GestureService.class)));
        Button open = new Button(this);
        open.setText("Open ADB 5 min");
        open.setOnClickListener(v -> startForegroundService(
                new Intent(this, GestureService.class).setAction(GestureService.ACTION_OPEN_ADB)));
        row.addView(start);
        row.addView(stop);
        row.addView(open);
        root.addView(row);

        ScrollView sv = new ScrollView(this);
        logView = new TextView(this);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextSize(14);
        sv.addView(logView);
        root.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        setContentView(root);

        startForegroundService(new Intent(this, GestureService.class));
        refresh();
    }

    private void refresh() {
        status.setText(GestureService.running ? "Service: running" : "Service: stopped");
        try {
            logView.setText(new String(GestureService.readAll(GestureService.logFile(this)), "UTF-8"));
        } catch (Exception e) {
            logView.setText("(no log yet)");
        }
        h.postDelayed(this::refresh, 1500);
    }

    @Override protected void onDestroy() {
        h.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
