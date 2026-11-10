package id.jaylabb.climategesture;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.view.Gravity;
import android.view.SoundEffectConstants;
import android.view.WindowManager;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * Background service. Root comes from the head unit's own adbd (127.0.0.1:5555, ro.adb.secure=0):
 *  - "touch" thread streams raw input_event structs from /dev/input/event0 and feeds GestureTracker;
 *  - "car" thread reads the A/C state on arm and writes fan / temperature (latest value wins);
 *  - the HUD is a non-touchable overlay, added only while a gesture runs.
 */
public class GestureService extends Service implements GestureTracker.Listener {
    static final String CHANNEL = "cg";
    static final String PKG = "id.jaylabb.climategesture";
    static final String TOUCH_DEV = "/dev/input/event0";
    static final int EV_SIZE = 24; // arm64: timeval(16) + type(2) + code(2) + value(4)

    static volatile boolean running;
    // read by MainActivity
    static volatile String carState = "connecting";   // connecting | ok | unsupported | error
    static volatile int stFan = -1, stTemp = -1;
    static volatile long adbOpenUntil;                 // 0 = port 5555 is loopback-only
    static volatile String removeMsg;                  // set when an uninstall did not go through
    static volatile boolean paused;

    private final Handler ui = new Handler(Looper.getMainLooper());
    private GestureTracker tracker;
    private HudView hud;
    private WindowManager wm;
    private boolean hudShown;
    private volatile boolean stop;
    private final Runnable hideR = this::hideIfIdle;

    // car-thread state, guarded by `lock`
    private final Object lock = new Object();
    private boolean needRead;
    private int baseFan = 4, baseTemp = 15, climateOn = 1;
    private boolean baseKnown;
    private int fanSteps, tempSteps;
    private int wantFan = -1, wantTemp = -1, sentFan = -1, sentTemp = -1;
    private boolean adbOpenReq, adbCloseReq, removeReq;

    static final String ACTION_OPEN_ADB = PKG + ".OPEN_ADB";
    static final String ACTION_CLOSE_ADB = PKG + ".CLOSE_ADB";
    static final String ACTION_REMOVE = PKG + ".REMOVE";
    static final long ADB_OPEN_MS = 5 * 60_000;

    static boolean pausedPref(Context c) {
        return c.getSharedPreferences("cg", MODE_PRIVATE).getBoolean("paused", false);
    }

    static void setPaused(Context c, boolean p) {
        c.getSharedPreferences("cg", MODE_PRIVATE).edit().putBoolean("paused", p).apply();
        paused = p;
        log(c, p ? "gestures paused" : "gestures on");
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Climate gesture", NotificationManager.IMPORTANCE_MIN));
        startForeground(1, new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_menu_compass)
                .setContentTitle("Climate gesture")
                .setContentText("Hold 2 fingers, then slide: ↔ fan, ↕ temperature")
                .build());
        paused = pausedPref(this);
        String act = intent == null ? null : intent.getAction();
        if (ACTION_OPEN_ADB.equals(act)) {
            // set the deadline now, so a fresh start skips the initial lock (an installer is still connected)
            synchronized (lock) {
                adbOpenReq = true;
                adbOpenUntil = System.currentTimeMillis() + ADB_OPEN_MS;
                lock.notifyAll();
            }
        } else if (ACTION_CLOSE_ADB.equals(act)) {
            synchronized (lock) { adbCloseReq = true; lock.notifyAll(); }
        } else if (ACTION_REMOVE.equals(act)) {
            removeMsg = null;
            synchronized (lock) { removeReq = true; lock.notifyAll(); }
        }
        if (!running) {
            running = true;
            stop = false;
            wm = getSystemService(WindowManager.class);
            hud = new HudView(this);
            tracker = new GestureTracker(this);
            new Thread(this::touchLoop, "cg-touch").start();
            new Thread(this::carLoop, "cg-car").start();
            new Thread(this::tickLoop, "cg-tick").start();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        stop = true;
        running = false;
        synchronized (lock) { lock.notifyAll(); }
        ui.post(this::hideNow);
        super.onDestroy();
    }

    // ---------------- touch ----------------
    private void touchLoop() {
        int fails = 0;
        while (!stop) {
            AdbClient c = null;
            try {
                c = new AdbClient("127.0.0.1", 5555, 8000);
                c.connect(loadOrCreateKey(getFilesDir()), "climategesture@headunit", null);
                // let our own overlay draw without the settings page
                c.shell("appops set " + PKG + " SYSTEM_ALERT_WINDOW allow");
                String caps = c.shell("getevent -pl " + TOUCH_DEV);
                java.util.regex.Matcher m = java.util.regex.Pattern
                        .compile("ABS_MT_SLOT +: +value ([0-9]+)").matcher(caps);
                int slot = m.find() ? Integer.parseInt(m.group(1)) : 0;
                synchronized (tracker) { tracker.setSlot(slot); }
                log(this, "touch stream open (" + TOUCH_DEV + ", slot " + slot + ")");
                fails = 0;
                final byte[] buf = new byte[EV_SIZE * 64];
                final int[] fill = {0};
                c.stream("exec cat " + TOUCH_DEV, data -> {
                    int off = 0;
                    while (off < data.length) {
                        int n = Math.min(buf.length - fill[0], data.length - off);
                        System.arraycopy(data, off, buf, fill[0], n);
                        fill[0] += n;
                        off += n;
                        int p = 0;
                        long now = System.currentTimeMillis();
                        synchronized (tracker) {
                            for (; p + EV_SIZE <= fill[0]; p += EV_SIZE) {
                                int type = (buf[p + 16] & 0xff) | (buf[p + 17] & 0xff) << 8;
                                int code = (buf[p + 18] & 0xff) | (buf[p + 19] & 0xff) << 8;
                                int value = (buf[p + 20] & 0xff) | (buf[p + 21] & 0xff) << 8
                                        | (buf[p + 22] & 0xff) << 16 | (buf[p + 23] & 0xff) << 24;
                                tracker.onEvent(type, code, value, now);
                            }
                        }
                        System.arraycopy(buf, p, buf, 0, fill[0] - p);
                        fill[0] -= p;
                    }
                    if (stop) throw new IOException("stopped");
                });
                log(this, "touch stream closed");
            } catch (Exception e) {
                if (!stop && (fails++ < 3 || fails % 20 == 0)) log(this, "touch: " + e);
            } finally {
                if (c != null) c.close();
            }
            sleep(fails < 5 ? 2000 : 10000);
        }
    }

    private void tickLoop() {
        while (!stop) {
            synchronized (tracker) { tracker.tick(System.currentTimeMillis()); }
            sleep(40);
        }
    }

    // ---------------- gesture callbacks (touch thread) ----------------
    @Override public void onArm() {
        if (paused) return;
        synchronized (lock) {
            needRead = true;
            baseKnown = false;
            fanSteps = tempSteps = 0;
            wantFan = wantTemp = -1;
            lock.notifyAll();
        }
        ui.post(() -> {
            hud.mode = HudView.MODE_BOTH;
            hud.fan = baseFan;
            hud.temp = baseTemp;
            show();
        });
    }

    @Override public void onFan(int steps) {
        if (paused) return;
        int v;
        synchronized (lock) {
            fanSteps = steps;
            v = clamp(baseFan + steps, Car.FAN_MIN, Car.FAN_MAX);
            if (baseKnown) { wantFan = v; lock.notifyAll(); }
        }
        final int fv = v;
        ui.post(() -> { hud.mode = HudView.MODE_FAN; if (hud.fan != fv) click(); hud.fan = fv; hud.invalidate(); });
    }

    @Override public void onTemp(int steps) {
        if (paused) return;
        int v;
        synchronized (lock) {
            tempSteps = steps;
            v = clamp(baseTemp + steps, Car.TEMP_MIN, Car.TEMP_MAX);
            if (baseKnown) { wantTemp = v; lock.notifyAll(); }
        }
        final int tv = v;
        ui.post(() -> { hud.mode = HudView.MODE_TEMP; if (hud.temp != tv) click(); hud.temp = tv; hud.invalidate(); });
    }

    @Override public void onEnd() {
        ui.removeCallbacks(hideR);
        ui.postDelayed(hideR, 900);
    }

    // ---------------- car ----------------
    private void carLoop() {
        while (!stop) {
            AdbClient c = null;
            try {
                c = new AdbClient("127.0.0.1", 5555, 8000);
                c.connect(loadOrCreateKey(getFilesDir()), "climategesture@headunit", null);
                Car car = new Car(c);
                Car.State st = car.read();
                if (st.ok()) synchronized (lock) { baseFan = st.fan; baseTemp = st.temp; climateOn = st.on; }
                carState = st.ok() ? "ok" : "unsupported";
                stFan = st.fan; stTemp = st.temp;
                log(this, "car link ok (" + (car.root() ? "root" : "via su") + "): on=" + st.on + " fan=" + st.fan + " temp=" + st.temp);
                if (!st.ok()) log(this, "climate properties not found: this head unit is not supported, gestures will not write");
                // adbd has no auth here (ro.adb.secure=0): keep 5555 reachable from loopback only
                synchronized (lock) { if (adbOpenUntil == 0) log(this, car.adbLocalOnly(true)); }
                while (!stop) {
                    boolean read, openReq, relock, remove;
                    int f, t;
                    synchronized (lock) {
                        while (!stop && !needRead && !adbOpenReq && !adbCloseReq && !removeReq
                                && wantFan == sentFan && wantTemp == sentTemp
                                && !(adbOpenUntil > 0 && System.currentTimeMillis() >= adbOpenUntil)) {
                            lock.wait(adbOpenUntil > 0 ? Math.max(1, adbOpenUntil - System.currentTimeMillis()) : 30_000);
                        }
                        read = needRead;
                        needRead = false;
                        openReq = adbOpenReq;
                        adbOpenReq = false;
                        relock = adbOpenUntil > 0 && (adbCloseReq || System.currentTimeMillis() >= adbOpenUntil);
                        adbCloseReq = false;
                        remove = removeReq;
                        removeReq = false;
                        if (openReq) adbOpenUntil = System.currentTimeMillis() + ADB_OPEN_MS;
                        else if (relock) adbOpenUntil = 0;
                    }
                    if (stop) break;
                    if (remove) {
                        // give port 5555 back as it was, then uninstall ourselves (this process ends here)
                        log(this, car.adbLocalOnly(false));
                        log(this, "removing Climate Gesture");
                        String out = car.uninstallSelf();
                        log(this, "uninstall: " + out);
                        if (out.contains("Success")) { stop = true; break; }   // we are being killed; leave 5555 as it was
                        removeMsg = out.isEmpty() ? "No answer from the package manager" : out;
                        synchronized (lock) { if (adbOpenUntil == 0) log(this, car.adbLocalOnly(true)); }
                        continue;
                    }
                    if (openReq) log(this, car.adbLocalOnly(false) + " for 5 min");
                    else if (relock) log(this, car.adbLocalOnly(true));
                    if (read) {
                        st = car.read();
                        synchronized (lock) {
                            if (st.ok()) { baseFan = Math.max(1, st.fan); baseTemp = st.temp; climateOn = st.on; }
                            carState = st.ok() ? "ok" : "unsupported";
                            stFan = st.fan; stTemp = st.temp;
                            baseKnown = st.ok(); // unknown head unit: show the HUD but never write
                            sentFan = sentTemp = -1;
                            // steps that arrived while we were reading
                            wantFan = baseKnown && fanSteps != 0 ?clamp(baseFan + fanSteps, Car.FAN_MIN, Car.FAN_MAX) : -1;
                            wantTemp = baseKnown && tempSteps != 0 ?clamp(baseTemp + tempSteps, Car.TEMP_MIN, Car.TEMP_MAX) : -1;
                        }
                        final int df, dt;
                        synchronized (lock) {
                            df = wantFan > 0 ? wantFan : baseFan;
                            dt = wantTemp >= 0 ? wantTemp : baseTemp;
                        }
                        ui.post(() -> { hud.fan = df; hud.temp = dt; hud.invalidate(); });
                    }
                    synchronized (lock) { f = wantFan; t = wantTemp; }
                    if (f > 0 && f != sentFan) {
                        boolean on = climateOn == 1;
                        car.setFan(f, on);
                        stFan = f;
                        synchronized (lock) { sentFan = f; climateOn = 1; }
                        log(this, "fan -> " + f + (on ? "" : " (climate on)"));
                    }
                    if (t >= 0 && t != sentTemp) {
                        car.setTemp(t);
                        stTemp = t;
                        synchronized (lock) { sentTemp = t; }
                        log(this, "temp -> " + Car.tempLabel(t) + " C");
                    }
                }
            } catch (Exception e) {
                if (!stop) { log(this, "car: " + e); carState = "error"; }
            } finally {
                if (c != null) c.close();
            }
            sleep(3000);
        }
    }

    // ---------------- HUD ----------------
    private void show() {
        ui.removeCallbacks(hideR);
        hud.animate().cancel();
        if (!hudShown) {
            WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                    HudView.W, HudView.H,
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                            | WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                            | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                    PixelFormat.TRANSLUCENT);
            lp.gravity = Gravity.CENTER;
            lp.y = -160;
            try {
                wm.addView(hud, lp);
                hudShown = true;
            } catch (Exception e) {
                log(this, "overlay: " + e);
                return;
            }
            hud.setAlpha(0f);
            hud.setScaleX(0.94f);
            hud.setScaleY(0.94f);
        }
        hud.animate().alpha(1f).scaleX(1f).scaleY(1f).setDuration(140).start();
        hud.invalidate();
    }

    private void hideIfIdle() {
        boolean armed;
        synchronized (tracker) { armed = tracker.armed(); }
        if (armed || !hudShown) return;
        hud.animate().alpha(0f).scaleX(0.96f).scaleY(0.96f).setDuration(220).withEndAction(this::hideNow).start();
    }

    private void hideNow() {
        if (!hudShown) return;
        try { wm.removeView(hud); } catch (Exception ignored) { }
        hudShown = false;
    }

    private void click() {
        hud.playSoundEffect(SoundEffectConstants.CLICK);
    }

    // ---------------- helpers ----------------
    private static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) { }
    }

    static KeyPair loadOrCreateKey(File dir) throws Exception {
        File pr = new File(dir, "adbkey.pk8"), pu = new File(dir, "adbkey.x509");
        KeyFactory kf = KeyFactory.getInstance("RSA");
        if (pr.exists() && pu.exists()) {
            return new KeyPair(kf.generatePublic(new X509EncodedKeySpec(readAll(pu))),
                    kf.generatePrivate(new PKCS8EncodedKeySpec(readAll(pr))));
        }
        KeyPairGenerator g = KeyPairGenerator.getInstance("RSA");
        g.initialize(2048);
        KeyPair kp = g.generateKeyPair();
        write(pr, kp.getPrivate().getEncoded(), false);
        write(pu, kp.getPublic().getEncoded(), false);
        return kp;
    }

    static File logFile(Context c) { return new File(c.getFilesDir(), "log.txt"); }

    static synchronized void log(Context c, String line) {
        String ts = new SimpleDateFormat("MM-dd HH:mm:ss", Locale.US).format(new Date());
        try {
            File f = logFile(c);
            if (f.length() > 32_000) f.delete();
            write(f, (ts + "  " + line + "\n").getBytes("UTF-8"), true);
        } catch (IOException ignored) { }
    }

    static byte[] readAll(File f) throws IOException {
        byte[] b = new byte[(int) f.length()];
        try (FileInputStream in = new FileInputStream(f)) {
            int off = 0, n;
            while (off < b.length && (n = in.read(b, off, b.length - off)) > 0) off += n;
        }
        return b;
    }

    static void write(File f, byte[] data, boolean append) throws IOException {
        try (FileOutputStream o = new FileOutputStream(f, append)) { o.write(data); }
    }
}
