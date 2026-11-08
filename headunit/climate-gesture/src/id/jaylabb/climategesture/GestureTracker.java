package id.jaylabb.climategesture;

/**
 * Turns raw multi-touch evdev events (protocol B: slots + tracking ids) into a climate gesture.
 *
 * Gesture: put two fingers down and hold them still for HOLD_MS. That arms it. Then drag:
 * the first clear direction locks the axis. Left/right = fan, up/down = temperature (up = warmer).
 * Values are reported as whole steps from the point where the gesture armed.
 * A pinch or a two-finger pan that starts moving straight away (maps) never arms.
 *
 * Pure Java (no Android) so it can be tested on the laptop. Not thread-safe: call from one thread.
 */
final class GestureTracker {
    interface Listener {
        void onArm();
        void onFan(int steps);   // total steps since arm, + = more fan
        void onTemp(int steps);  // total steps since arm, + = warmer
        void onEnd();            // fingers lifted after arming
    }

    static final int EV_SYN = 0, EV_KEY = 1, EV_ABS = 3, BTN_TOUCH = 0x14a;
    static final int ABS_MT_SLOT = 0x2f, ABS_MT_POSITION_X = 0x35, ABS_MT_POSITION_Y = 0x36,
            ABS_MT_TRACKING_ID = 0x39;

    // Screen is 1440 x 1920 px; touch coordinates map 1:1.
    long holdMs = 280;        // two fingers still this long -> armed
    float holdSlop = 45;      // px any finger may drift while holding
    float axisLock = 55;      // px of travel before the axis locks
    float fanStep = 85;       // px per fan level
    float tempStep = 60;      // px per 0.5 degC
    float axisSwitch = 110;   // px across the locked axis that switches to the other one
    long staleMs = 4000;      // armed but no events this long -> treat as lifted

    private enum S { IDLE, WAIT, ARMED, FAN, TEMP, REJECT }

    private static final int MAX = 10;
    private final int[] tid = new int[MAX];
    private final float[] x = new float[MAX], y = new float[MAX];
    private final float[] sx = new float[MAX], sy = new float[MAX];
    private int slot;
    private S s = S.IDLE;
    private long t0;
    private float ax, ay;
    private int last;
    private int fanAcc, tempAcc;   // steps kept from earlier legs when the axis switches
    private boolean allUp;
    private long lastEv;
    private final Listener l;

    GestureTracker(Listener l) {
        this.l = l;
        for (int i = 0; i < MAX; i++) tid[i] = -1;
    }

    /** The kernel drops ABS_MT_SLOT events equal to the current slot, so a reader that starts
     *  mid-stream must be told the current slot (from `getevent -p`), or contacts land in the wrong slot. */
    void setSlot(int v) { slot = (v >= 0 && v < MAX) ? v : 0; }

    boolean armed() { return s == S.ARMED || s == S.FAN || s == S.TEMP; }

    void onEvent(int type, int code, int value, long nowMs) {
        lastEv = nowMs;
        if (type == EV_KEY && code == BTN_TOUCH && value == 0) {
            allUp = true;
        } else if (type == EV_ABS) {
            switch (code) {
                case ABS_MT_SLOT: slot = (value >= 0 && value < MAX) ? value : 0; break;
                case ABS_MT_TRACKING_ID: tid[slot] = value; break;
                case ABS_MT_POSITION_X: x[slot] = value; break;
                case ABS_MT_POSITION_Y: y[slot] = value; break;
                default: break;
            }
        } else if (type == EV_SYN && code == 0) {
            if (allUp) { // nothing touches the screen: drop any contact we lost track of
                allUp = false;
                for (int i = 0; i < MAX; i++) tid[i] = -1;
            }
            frame(nowMs);
        }
    }

    /** Call every ~40 ms: a finger held perfectly still may produce no events at all. */
    void tick(long nowMs) {
        if (s == S.WAIT) frame(nowMs);
        else if (armed() && nowMs - lastEv > staleMs) { s = S.REJECT; l.onEnd(); }
    }

    private void frame(long now) {
        int n = 0;
        float cx = 0, cy = 0;
        for (int i = 0; i < MAX; i++) {
            if (tid[i] >= 0) { n++; cx += x[i]; cy += y[i]; }
        }
        if (n > 0) { cx /= n; cy /= n; }

        switch (s) {
            case IDLE:
                if (n == 2) {
                    s = S.WAIT;
                    t0 = now;
                    for (int i = 0; i < MAX; i++) { sx[i] = x[i]; sy[i] = y[i]; }
                } else if (n > 2) {
                    s = S.REJECT;
                }
                break;
            case WAIT:
                if (n != 2) { s = n == 0 ? S.IDLE : S.REJECT; break; }
                for (int i = 0; i < MAX; i++) {
                    if (tid[i] >= 0 && Math.hypot(x[i] - sx[i], y[i] - sy[i]) > holdSlop) {
                        s = S.REJECT;
                        return;
                    }
                }
                if (now - t0 >= holdMs) {
                    s = S.ARMED;
                    ax = cx;
                    ay = cy;
                    last = fanAcc = tempAcc = 0;
                    l.onArm();
                }
                break;
            case ARMED:
            case FAN:
            case TEMP:
                if (n == 0) { s = S.IDLE; l.onEnd(); break; }
                if (n != 2) break; // one finger lifting first, or a stray third: ignore the frame
                float dx = cx - ax, dy = cy - ay;
                if (s == S.ARMED) {
                    if (Math.abs(dx) < axisLock && Math.abs(dy) < axisLock) break;
                    s = Math.abs(dx) >= Math.abs(dy) ? S.FAN : S.TEMP;
                    if (s == S.FAN) ay = cy; else ax = cx; // cross-axis drift counts from here
                    last = s == S.FAN ? fanAcc : tempAcc;
                } else if (s == S.FAN && Math.abs(cy - ay) > axisSwitch) {
                    // ay is where the fan leg began, so the travel that switched us already counts
                    fanAcc = last; s = S.TEMP; ax = cx; last = tempAcc;
                } else if (s == S.TEMP && Math.abs(cx - ax) > axisSwitch) {
                    tempAcc = last; s = S.FAN; ay = cy; last = fanAcc;
                }
                int steps = s == S.FAN ? fanAcc + (int) ((cx - ax) / fanStep) : tempAcc + (int) (-(cy - ay) / tempStep);
                if (steps != last) {
                    last = steps;
                    if (s == S.FAN) l.onFan(steps); else l.onTemp(steps);
                }
                break;
            case REJECT:
                if (n == 0) s = S.IDLE;
                break;
        }
    }
}
