package cv.sarthakgoel.tvhome;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Live weather for the ambient wallpaper, the Home-press weather effect and the temperature after the date.
 * Open-Meteo (free, no key) is read on a background thread at most every 30 minutes; the last answer is kept
 * in SharedPreferences, so a restart or a dead network falls back to it, and past {@link #STALE_MS} to the
 * time of day alone. Nothing here ever runs on the main thread or throws to its caller.
 */
final class Weather {
    private static final String TAG = "TvHome.Weather";
    private static final String PREFS = "weather";
    static final long REFRESH_MS = 30 * 60_000L;
    /** Older than this, a cached reading no longer describes the sky outside. */
    static final long STALE_MS = 3 * 60 * 60_000L;
    private static final int TIMEOUT_MS = 8000;

    /** Conditions, the names of the weather effects too. */
    static final String CLEAR = "clear", CLOUDY = "cloudy", RAIN = "rain", STORM = "storm", FOG = "fog",
            HOT = "hot", COLD = "cold";

    /** Fallback sunrise and sunset, minutes after midnight, when no forecast is known. */
    static final int SUNRISE_FALLBACK = 6 * 60 + 15, SUNSET_FALLBACK = 18 * 60;

    final double tempC;
    final int code;
    final boolean isDay;
    final int cloudCover;
    final double pm25;
    /** Minutes after midnight, local time at the location. */
    final int sunrise, sunset;
    final long fetchedAt;

    Weather(double tempC, int code, boolean isDay, int cloudCover, double pm25, int sunrise, int sunset, long fetchedAt) {
        this.tempC = tempC;
        this.code = code;
        this.isDay = isDay;
        this.cloudCover = cloudCover;
        this.pm25 = pm25;
        this.sunrise = sunrise;
        this.sunset = sunset;
        this.fetchedAt = fetchedAt;
    }

    String condition() {
        return condition(code, tempC, isDay, cloudCover, pm25);
    }

    boolean fresh(long now) {
        return now - fetchedAt < STALE_MS && now >= fetchedAt - 60_000L;
    }

    // ---------------------------------------------------------------- pure mapping

    /** WMO weather code and readings to one of the condition names. pm25 below 0 means unknown. */
    static String condition(int code, double tempC, boolean isDay, int cloudCover, double pm25) {
        if (code >= 95 && code <= 99) return STORM;
        if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return RAIN;
        if (code == 45 || code == 48 || pm25 > 150) return FOG;               // smog reads as fog
        if ((code >= 71 && code <= 77) || code == 85 || code == 86) return COLD; // no snow art: cold
        if (tempC >= 38 && isDay) return HOT;
        if (tempC <= 8) return COLD;
        if (cloudCover >= 75 || code == 3) return CLOUDY;
        return CLEAR;
    }

    /** dawn, day, dusk or night at {@code minute} after midnight, from the day's sunrise and sunset. */
    static String slot(int minute, int sunrise, int sunset) {
        if (minute >= sunrise - 45 && minute < sunrise + 75) return "dawn";
        if (minute >= sunset - 60 && minute < sunset + 40) return "dusk";
        if (minute >= sunrise + 75 && minute < sunset - 60) return "day";
        return "night";
    }

    /** The ambient/&lt;name&gt;.jpg for a condition (null: time of day only) in a time slot. */
    static String ambient(String condition, String slot) {
        boolean night = "night".equals(slot);
        if (condition == null) condition = CLEAR;
        switch (condition) {
            case STORM: return "storm";
            case RAIN: return night ? "rain-night" : "rain-day";
            case FOG: return "fog";
            case HOT: return night ? "night" : "hot";
            case COLD: return night ? "night" : "cold";
            case CLOUDY: return night ? "cloudy-night" : "cloudy-day";
            default: return slot;   // clear: dawn, day, dusk or night
        }
    }

    // ---------------------------------------------------------------- cache

    static Weather cached(Context ctx) {
        SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String raw = p.getString("last", null);
        if (raw == null) return null;
        try {
            JSONObject o = new JSONObject(raw);
            return new Weather(o.getDouble("t"), o.getInt("c"), o.getBoolean("d"), o.getInt("cc"),
                    o.optDouble("pm", -1), o.getInt("sr"), o.getInt("ss"), o.getLong("at"));
        } catch (Exception e) {
            return null;
        }
    }

    private static void store(Context ctx, Weather w) {
        try {
            JSONObject o = new JSONObject();
            o.put("t", w.tempC).put("c", w.code).put("d", w.isDay).put("cc", w.cloudCover).put("pm", w.pm25)
                    .put("sr", w.sunrise).put("ss", w.sunset).put("at", w.fetchedAt);
            ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString("last", o.toString()).apply();
        } catch (Exception ignored) {
            // a reading we cannot keep is still shown this time
        }
    }

    // ---------------------------------------------------------------- network (background thread only)

    /** Fetches the current weather, caches it and returns it; null on any failure. */
    static Weather fetch(Context ctx, String lat, String lon) {
        try {
            String q = "latitude=" + lat + "&longitude=" + lon;
            JSONObject f = new JSONObject(get("https://api.open-meteo.com/v1/forecast?" + q
                    + "&current=temperature_2m,weather_code,is_day,cloud_cover,precipitation,wind_speed_10m"
                    + "&daily=sunrise,sunset&timezone=auto&forecast_days=1"));
            JSONObject cur = f.getJSONObject("current");
            JSONObject daily = f.optJSONObject("daily");
            int sunrise = SUNRISE_FALLBACK, sunset = SUNSET_FALLBACK;
            if (daily != null) {
                sunrise = minuteOf(first(daily.optJSONArray("sunrise")), SUNRISE_FALLBACK);
                sunset = minuteOf(first(daily.optJSONArray("sunset")), SUNSET_FALLBACK);
            }
            double pm25 = -1;
            try {
                JSONObject aq = new JSONObject(get("https://air-quality-api.open-meteo.com/v1/air-quality?" + q
                        + "&current=pm2_5"));
                pm25 = aq.getJSONObject("current").optDouble("pm2_5", -1);
            } catch (Exception e) {
                Log.i(TAG, "air quality unavailable: " + e.getClass().getSimpleName());
            }
            Weather w = new Weather(cur.getDouble("temperature_2m"), cur.getInt("weather_code"),
                    cur.optInt("is_day", 1) == 1, cur.optInt("cloud_cover", 0), Double.isNaN(pm25) ? -1 : pm25,
                    sunrise, sunset, System.currentTimeMillis());
            store(ctx, w);
            Log.i(TAG, "weather: " + w.condition() + " " + Math.round(w.tempC) + "C code=" + w.code
                    + " day=" + w.isDay + " cloud=" + w.cloudCover + " pm2_5=" + Math.round(w.pm25)
                    + " precip=" + cur.optDouble("precipitation", 0) + " wind=" + cur.optDouble("wind_speed_10m", 0)
                    + " sunrise=" + hhmm(sunrise) + " sunset=" + hhmm(sunset));
            return w;
        } catch (Exception e) {
            Log.w(TAG, "weather fetch failed: " + e.getClass().getSimpleName());
            return null;
        }
    }

    private static String first(JSONArray a) {
        return a == null || a.length() == 0 ? null : a.optString(0, null);
    }

    /** "2026-10-21T06:29" to minutes after midnight. */
    static int minuteOf(String iso, int fallback) {
        if (iso == null) return fallback;
        int t = iso.indexOf('T');
        if (t < 0 || iso.length() < t + 6) return fallback;
        try {
            int h = Integer.parseInt(iso.substring(t + 1, t + 3));
            int m = Integer.parseInt(iso.substring(t + 4, t + 6));
            return h >= 0 && h < 24 && m >= 0 && m < 60 ? h * 60 + m : fallback;
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    private static String hhmm(int minute) {
        return String.format(java.util.Locale.ROOT, "%02d:%02d", minute / 60, minute % 60);
    }

    private static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(TIMEOUT_MS);
        c.setReadTimeout(TIMEOUT_MS);
        c.setUseCaches(false);
        try {
            if (c.getResponseCode() != 200) throw new java.io.IOException("HTTP " + c.getResponseCode());
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buf = new byte[4096];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                    if (out.size() > 256 * 1024) throw new java.io.IOException("response too large");
                }
                return new String(out.toByteArray(), StandardCharsets.UTF_8);
            }
        } finally {
            c.disconnect();
        }
    }
}
