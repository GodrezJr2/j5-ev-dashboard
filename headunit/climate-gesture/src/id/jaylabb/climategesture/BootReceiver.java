package id.jaylabb.climategesture;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        GestureService.log(c, "start on " + i.getAction());
        Intent s = new Intent(c, GestureService.class);
        // an update arrives over ADB: keep port 5555 reachable for 5 min so the installer can finish
        if (Intent.ACTION_MY_PACKAGE_REPLACED.equals(i.getAction())) s.setAction(GestureService.ACTION_OPEN_ADB);
        c.startForegroundService(s);
    }
}
