package id.jaylabb.climategesture;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Reads and writes the A/C through the vehicle HAL with `lshal debug` over the head unit's own root adbd.
 * Same properties and order as the stock systemui (CarHvacClient); verified on the car 8 Nov 2026.
 */
final class Car {
    static final String HAL = "android.hardware.automotive.vehicle@2.0::IVehicle/default";

    // reads (car -> head unit)
    static final int WORKINGSTS_51A = 557847217;          // 1 = climate on
    static final int BLOWSPEED_DISPLAY_535 = 557847208;   // fan level shown, 1..10
    static final int TEMP_L_51A = 557847225;              // temp step, degC = 15.5 + step/2
    // writes (head unit -> car)
    static final int SETCLMON_519 = 557848344;
    static final int BLOWSPEED_KEY_4F9 = 557848251;
    static final int SETTEMP_L_519 = 557848335, SETTEMP_R_519 = 557848339;
    static final int MERGE_FRAME = 557914148;

    static final int FAN_MIN = 1, FAN_MAX = 10, TEMP_MIN = 0, TEMP_MAX = 30;

    static final class State {
        int on = -1, fan = -1, temp = -1;
        boolean ok() { return fan >= 0 && temp >= 0; }
    }

    private final AdbClient adb;
    private final boolean root;

    /** After a reboot adbd may run as uid shell (no `adb root`); lshal needs root, so go through su. */
    Car(AdbClient adb) throws Exception {
        this.adb = adb;
        this.root = "0".equals(adb.shell("id -u").trim());
    }

    boolean root() { return root; }

    private String sh(String cmd) throws Exception {
        return adb.shell(root ? cmd : "su 0 sh -c '" + cmd + "'");
    }

    State read() throws Exception {
        String out = sh("H=" + HAL + "; for p in " + WORKINGSTS_51A + " " + BLOWSPEED_DISPLAY_535 + " "
                + TEMP_L_51A + "; do lshal debug $H --get $p 2>&1; done");
        State st = new State();
        Matcher m = Pattern.compile("\\.prop = (\\d+).*?int32Values = \\[1\\]\\{(-?\\d+)\\}").matcher(out);
        while (m.find()) {
            int p = Integer.parseInt(m.group(1)), v = Integer.parseInt(m.group(2));
            if (p == WORKINGSTS_51A) st.on = v;
            else if (p == BLOWSPEED_DISPLAY_535) st.fan = v;
            else if (p == TEMP_L_51A) st.temp = v;
        }
        return st;
    }

    void setFan(int level, boolean climateOn) throws Exception {
        level = Math.max(FAN_MIN, Math.min(FAN_MAX, level));
        String cmd = "H=" + HAL + "; ";
        if (!climateOn) cmd += set(SETCLMON_519, "1") + "; ";
        sh(cmd + set(BLOWSPEED_KEY_4F9, String.valueOf(level)));
    }

    /** Single-zone A/C: left and right go out together in one CAN frame. */
    void setTemp(int step) throws Exception {
        step = Math.max(TEMP_MIN, Math.min(TEMP_MAX, step));
        String v = String.valueOf(step);
        sh("H=" + HAL + "; " + set(MERGE_FRAME, SETTEMP_L_519 + " i " + SETTEMP_R_519) + "; "
                + set(SETTEMP_L_519, v) + "; " + set(SETTEMP_R_519, v));
    }

    private static String set(int prop, String v) {
        return "lshal debug $H --set " + prop + " i " + v + " >/dev/null 2>&1";
    }

    // adbd listens on every interface with no auth. DROP 5555 unless it comes in on loopback, so the
    // wireless CarPlay AP or a WiFi network can't reach it; our app and carplay60 use 127.0.0.1.
    private static final String RULE = "INPUT -p tcp --dport 5555 ! -i lo -j DROP";

    String adbLocalOnly(boolean on) throws Exception {
        String cmd = on
                ? "for t in iptables ip6tables; do $t -C " + RULE + " 2>/dev/null || $t -I " + RULE + "; done"
                : "for t in iptables ip6tables; do while $t -D " + RULE + " 2>/dev/null; do :; done; done";
        String out = sh(cmd + " 2>&1").trim();
        return (on ? "adb 5555: loopback only" : "adb 5555: open to network") + (out.isEmpty() ? "" : " (" + out + ")");
    }

    /** `pm uninstall` of this app; the package manager kills our process once it goes through. */
    String uninstallSelf() throws Exception {
        return sh("pm uninstall " + GestureService.PKG + " 2>&1").trim();
    }

    static String tempLabel(int step) {
        double c = 15.5 + step / 2.0;
        return (c == Math.floor(c) ? String.valueOf((int) c) : String.valueOf(c));
    }
}
