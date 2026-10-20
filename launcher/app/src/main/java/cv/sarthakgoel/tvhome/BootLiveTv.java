package cv.sarthakgoel.tvhome;

import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;
import android.util.Log;

/**
 * Some MediaTek TVs (OnePlus Y Series) open Live TV once after every boot, whatever the default Home is
 * (ro.vendor.mtk.auto.enter.livetv, read in com.mediatek.tv.agent.LiveTVLauncher). With no antenna that is
 * a "Please Scan Channels!" screen. InputKeyService sees each new window; if Live TV is the first app to come
 * up in the minutes after boot, Home is brought back, once.
 */
final class BootLiveTv {
    private static final String TAG = "BootLiveTv";
    private static final String LIVE_TV = "com.mediatek.wwtv.tvcenter";
    private static final long BOOT_WINDOW_MS = 120_000;
    private static boolean sDecided;

    private BootLiveTv() {}

    static void onWindow(Context context, CharSequence pkg) {
        if (sDecided || pkg == null) return;
        if (SystemClock.elapsedRealtime() > BOOT_WINDOW_MS) { sDecided = true; return; }
        String p = pkg.toString();
        if (p.equals("android") || p.equals("com.android.systemui") || p.equals("com.android.tv.settings")) return;
        sDecided = true;
        if (!LIVE_TV.equals(p)) return;
        Intent home = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
                .setPackage(context.getPackageName()).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            context.startActivity(home);
            Log.i(TAG, "Live TV opened at boot; Home brought back");
        } catch (RuntimeException e) {
            Log.w(TAG, "could not bring Home back", e);
        }
    }
}
