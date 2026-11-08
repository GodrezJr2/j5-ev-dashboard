package id.jaylabb.climategesture;

import java.util.ArrayList;
import java.util.List;

public class TrackerTest {
    static List<String> got = new ArrayList<>();
    static GestureTracker t;
    static long now;

    static void ev(int ty, int c, int v) { t.onEvent(ty, c, v, now); }
    static void syn() { ev(0, 0, 0); }
    static void finger(int slot, int id, int x, int y) {
        ev(3, 0x2f, slot); if (id != Integer.MIN_VALUE) ev(3, 0x39, id); ev(3, 0x35, x); ev(3, 0x36, y);
    }
    static void lift(int slot) { ev(3, 0x2f, slot); ev(3, 0x39, -1); }
    static void hold(long ms) { for (long e = now + ms; now < e; now += 40) t.tick(now); }

    static void reset() {
        got.clear(); now = 1000;
        t = new GestureTracker(new GestureTracker.Listener() {
            public void onArm() { got.add("arm"); }
            public void onFan(int s) { got.add("fan" + s); }
            public void onTemp(int s) { got.add("temp" + s); }
            public void onEnd() { got.add("end"); }
        });
    }
    static void drag2(int dx, int dy, int steps) {
        for (int i = 1; i <= steps; i++) {
            now += 16;
            finger(0, Integer.MIN_VALUE, 500 + dx * i / steps, 900 + dy * i / steps);
            finger(1, Integer.MIN_VALUE, 700 + dx * i / steps, 900 + dy * i / steps);
            syn();
        }
    }
    static void down2() { finger(0, 10, 500, 900); finger(1, 11, 700, 900); syn(); }
    static void up2() { lift(0); syn(); lift(1); syn(); }
    static void check(String name, String want) {
        String g = String.join(",", got);
        System.out.println((g.equals(want) ? "PASS " : "FAIL ") + name + ": " + g + (g.equals(want) ? "" : "   want " + want));
    }

    public static void main(String[] a) {
        reset(); down2(); hold(320); drag2(260, 10, 20); up2();
        check("hold then right = fan +3", "arm,fan1,fan2,fan3,end");
        reset(); down2(); hold(320); drag2(-5, -190, 20); up2();
        check("hold then up = temp +3", "arm,temp1,temp2,temp3,end");
        reset(); down2(); hold(320); drag2(0, 130, 10); up2();
        check("hold then down = temp -2", "arm,temp-1,temp-2,end");
        reset(); down2(); drag2(300, 0, 10); hold(400); up2();
        check("immediate pan never arms", "");
        reset(); down2(); hold(100); up2();
        check("quick 2-finger tap", "");
        reset(); finger(0, 10, 500, 900); syn(); hold(400); drag2(300, 0, 10); lift(0); syn();
        check("one finger never arms", "");

        // kernel is on slot 1 when we start; first contact arrives without ABS_MT_SLOT
        reset(); t.setSlot(1);
        ev(3, 0x39, 20); ev(3, 0x35, 500); ev(3, 0x36, 900); ev(1, 0x14a, 1); syn();
        finger(0, 21, 700, 900); syn(); hold(320);
        for (int i = 1; i <= 10; i++) { now += 16; ev(3, 0x2f, 1); ev(3, 0x35, 500 + 26 * i); ev(3, 0x2f, 0); ev(3, 0x35, 700 + 26 * i); syn(); }
        ev(3, 0x2f, 1); ev(3, 0x39, -1); syn(); ev(3, 0x2f, 0); ev(3, 0x39, -1); ev(1, 0x14a, 0); syn();
        check("start on slot 1", "arm,fan1,fan2,fan3,end");
        // ghost: a contact we never saw lift; BTN_TOUCH 0 clears it
        reset(); finger(3, 99, 100, 100); syn(); ev(1, 0x14a, 0); syn();
        down2(); hold(320); drag2(260, 0, 20); up2();
        check("ghost cleared by BTN_TOUCH up", "arm,fan1,fan2,fan3,end");
        // up then right in one gesture keeps both
        reset(); down2(); hold(320); drag2(0, -130, 10);
        for (int i = 1; i <= 20; i++) { now += 16; finger(0, Integer.MIN_VALUE, 500 + 13 * i, 770); finger(1, Integer.MIN_VALUE, 700 + 13 * i, 770); syn(); }
        up2();
        check("temp then fan", "arm,temp1,temp2,fan1,fan2,fan3,end");
        // stale: armed, events stop -> end
        reset(); down2(); hold(320); hold(4200);
        check("stale ends", "arm,end");
    }
}
