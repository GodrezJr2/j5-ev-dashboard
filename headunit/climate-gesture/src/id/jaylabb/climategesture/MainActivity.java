package id.jaylabb.climategesture;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

/** Status, pause, ADB for updates, remove. Built in code (no layout XML, the build has no resource step). */
public class MainActivity extends Activity {
    // dark, like the head unit
    static final int BG = 0xFF0E1014, CARD = 0xFF191C22, LINE = 0xFF2A2E36, INK = 0xFFEEF0F3,
            MUT = 0xFF9AA1AC, ACC = 0xFF3CCB8A, WARN = 0xFFF2B544, BAD = 0xFFFF6B6B;

    private final Handler h = new Handler(Looper.getMainLooper());
    private TextView dot, stateT, stateS, adbT, adbS, logView, removeT;
    private Button adbBtn, logBtn;
    private Switch sw;
    private boolean removing;

    // the head unit is 1440 px wide at a low density, so plain dp comes out tiny: scale the layout to ~560 dp wide
    private float k = 1f;

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v * k, getResources().getDisplayMetrics());
    }

    private TextView text(String s, float sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp * k);
        t.setTextColor(color);
        t.setLineSpacing(0, 1.2f);
        if (bold) t.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        return t;
    }

    private GradientDrawable round(int fill, int stroke, float r) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(r));
        if (stroke != 0) g.setStroke(dp(1.5f), stroke);
        return g;
    }

    private LinearLayout card() {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setPadding(dp(22), dp(20), dp(22), dp(20));
        c.setBackground(round(CARD, 0, 18));
        return c;
    }

    private Button button(String s, int fill, int ink, int stroke) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        b.setTextSize(17 * k);
        b.setTextColor(ink);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        b.setBackground(round(fill, stroke, 14));
        b.setStateListAnimator(null);
        b.setPadding(dp(20), dp(12), dp(20), dp(12));
        b.setMinHeight(dp(52));
        return b;
    }

    private LinearLayout.LayoutParams gap(int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(top);
        return lp;
    }

    private View howRow(String glyph, String what, String value) {
        LinearLayout r = new LinearLayout(this);
        r.setGravity(Gravity.CENTER_VERTICAL);
        TextView g = text(glyph, 30, ACC, true);
        g.setGravity(Gravity.CENTER);
        g.setBackground(round(0xFF22362E, 0, 12));
        r.addView(g, new LinearLayout.LayoutParams(dp(48), dp(48)));
        LinearLayout t = new LinearLayout(this);
        t.setOrientation(LinearLayout.VERTICAL);
        t.setPadding(dp(16), 0, 0, 0);
        t.addView(text(what, 18, INK, true));
        t.addView(text(value, 15, MUT, false));
        r.addView(t);
        return r;
    }

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        k = Math.max(1f, Math.min(2.4f, dm.widthPixels / dm.density / 560f));
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(28), dp(28), dp(28), dp(36));

        // header
        String ver = "";
        try { PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0); ver = "v" + pi.versionName; }
        catch (Exception ignored) { }
        root.addView(text("Climate Gesture", 30, INK, true));
        root.addView(text(ver + "  ·  two-finger fan and temperature", 15, MUT, false), gap(4));

        // status
        LinearLayout st = card();
        LinearLayout sr = new LinearLayout(this);
        sr.setGravity(Gravity.CENTER_VERTICAL);
        dot = new TextView(this);
        sr.addView(dot, new LinearLayout.LayoutParams(dp(14), dp(14)));
        LinearLayout stt = new LinearLayout(this);
        stt.setOrientation(LinearLayout.VERTICAL);
        stt.setPadding(dp(14), 0, 0, 0);
        stateT = text("", 20, INK, true);
        stateS = text("", 15, MUT, false);
        stt.addView(stateT);
        stt.addView(stateS);
        sr.addView(stt, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        sw = new Switch(this);
        sw.setChecked(!GestureService.pausedPref(this));
        sw.setThumbTintList(new ColorStateList(new int[][]{{android.R.attr.state_checked}, {}}, new int[]{Color.WHITE, 0xFFB8BEC8}));
        sw.setTrackTintList(new ColorStateList(new int[][]{{android.R.attr.state_checked}, {}}, new int[]{ACC, LINE}));
        sw.setOnCheckedChangeListener((v, on) -> { GestureService.setPaused(this, !on); refresh(); });
        sw.setScaleX(k);
        sw.setScaleY(k);
        sr.addView(sw, new LinearLayout.LayoutParams(dp(60), dp(44)));
        st.addView(sr);
        root.addView(st, gap(24));

        // how to
        LinearLayout how = card();
        how.addView(text("Rest two fingers on the screen for a moment, then slide.", 16, MUT, false));
        how.addView(howRow("↔", "Slide sideways", "Fan speed 1 to 10"), gap(16));
        how.addView(howRow("↕", "Slide up or down", "Temperature 15.5 to 30.5 °C"), gap(12));
        how.addView(text("You can switch direction without lifting. A small card shows the value while you slide.", 14, MUT, false), gap(16));
        root.addView(how, gap(14));

        // ADB for updates
        LinearLayout adb = card();
        adb.addView(text("Updates from the laptop", 18, INK, true));
        adbT = text("", 16, INK, false);
        adb.addView(adbT, gap(8));
        adbS = text("While this app runs, the head unit's ADB port only answers inside the head unit. "
                + "Open it for 5 minutes before you update from the dashboard.", 14, MUT, false);
        adb.addView(adbS, gap(4));
        adbBtn = button("", 0xFF262A32, INK, 0);
        adbBtn.setOnClickListener(v -> startForegroundService(new Intent(this, GestureService.class)
                .setAction(GestureService.adbOpenUntil > 0 ? GestureService.ACTION_CLOSE_ADB : GestureService.ACTION_OPEN_ADB)));
        adb.addView(adbBtn, gap(14));
        root.addView(adb, gap(14));

        // remove
        LinearLayout rm = card();
        rm.addView(text("Remove", 18, INK, true));
        removeT = text("Takes the add-on off this head unit. Your A/C settings stay as they are, and you can install it again any time.",
                14, MUT, false);
        rm.addView(removeT, gap(4));
        Button rb = button("Remove Climate Gesture", CARD, BAD, 0x66FF6B6B);
        rb.setOnClickListener(v -> confirmRemove());
        rm.addView(rb, gap(14));
        root.addView(rm, gap(14));

        // log, hidden by default
        logBtn = button("Show log", BG, MUT, LINE);
        logBtn.setTextSize(15 * k);
        logBtn.setOnClickListener(v -> {
            boolean show = logView.getVisibility() != View.VISIBLE;
            logView.setVisibility(show ? View.VISIBLE : View.GONE);
            logBtn.setText(show ? "Hide log" : "Show log");
        });
        root.addView(logBtn, gap(20));
        logView = text("", 13, MUT, false);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextIsSelectable(true);
        logView.setBackground(round(CARD, 0, 14));
        logView.setPadding(dp(16), dp(14), dp(16), dp(14));
        logView.setVisibility(View.GONE);
        root.addView(logView, gap(10));

        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(BG);
        sv.setFillViewport(true);
        sv.addView(root);
        setContentView(sv);

        startForegroundService(new Intent(this, GestureService.class));
        refresh();
    }

    private void confirmRemove() {
        AlertDialog d = new AlertDialog.Builder(this, android.R.style.Theme_DeviceDefault_Dialog_Alert)
                .setTitle("Remove Climate Gesture?")
                .setMessage("The add-on is uninstalled and the ADB port goes back to how it was before.\n\n"
                        + "Your A/C settings stay as they are. If you no longer need it, switch Enable ADB off "
                        + "in Engineering mode afterwards.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Remove", (x, w) -> {
                    removing = true;
                    startForegroundService(new Intent(this, GestureService.class).setAction(GestureService.ACTION_REMOVE));
                    refresh();
                })
                .create();
        d.show();
        d.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(BAD);
    }

    private void refresh() {
        h.removeCallbacksAndMessages(null);
        String cs = GestureService.carState;
        boolean on = GestureService.running, paused = GestureService.paused;
        int c;
        String t, s;
        if (removing && GestureService.removeMsg == null) { c = WARN; t = "Removing…"; s = "This screen closes when it is done."; }
        else if (!on) { c = MUT; t = "Starting"; s = "The service is starting up."; }
        else if ("unsupported".equals(cs)) { c = BAD; t = "Not supported"; s = "This head unit does not expose the A/C the way the J5 does, so gestures never write."; }
        else if ("error".equals(cs) || "connecting".equals(cs)) { c = WARN; t = "Connecting to the car"; s = "Enable ADB must stay on in Engineering mode."; }
        else if (paused) { c = MUT; t = "Paused"; s = "Gestures are off. Turn the switch on to use them again."; }
        else {
            c = ACC; t = "Ready";
            int f = GestureService.stFan, tp = GestureService.stTemp;
            s = f >= 0 && tp >= 0 ? "Car now: fan " + f + "  ·  " + Car.tempLabel(tp) + " °C" : "Car link ok";
        }
        if (removing && GestureService.removeMsg != null) {
            c = BAD; t = "Could not remove"; s = GestureService.removeMsg;
            removing = false;
        }
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(c);
        dot.setBackground(g);
        stateT.setText(t);
        stateS.setText(s);

        long left = GestureService.adbOpenUntil - System.currentTimeMillis();
        if (GestureService.adbOpenUntil > 0 && left > 0) {
            long sec = left / 1000;
            adbT.setText(String.format(java.util.Locale.US, "Open to WiFi  ·  %d:%02d left", sec / 60, sec % 60));
            adbT.setTextColor(WARN);
            adbBtn.setText("Close now");
        } else {
            adbT.setText("Closed to WiFi");
            adbT.setTextColor(ACC);
            adbBtn.setText("Open for 5 minutes");
        }

        if (logView.getVisibility() == View.VISIBLE) {
            try { logView.setText(new String(GestureService.readAll(GestureService.logFile(this)), "UTF-8")); }
            catch (Exception e) { logView.setText("(no log yet)"); }
        }
        h.postDelayed(this::refresh, 1000);
    }

    @Override protected void onDestroy() {
        h.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
