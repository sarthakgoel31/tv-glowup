package cv.sarthakgoel.tvhome;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Family photos for the screensaver: image files in the app's external files folder, photos/, pushed from a
 * computer over adb (oneplus-tv/add_photos.sh resizes, rotates and strips location data first). Every photo is
 * in the screensaver unless the family took it out in Family Photos; the choice is kept as a set of names left
 * out, so a newly added photo is in by default.
 */
final class PhotoStore {
    static final String DIR = "photos";
    private static final String PREFS = "family_photos", LEFT_OUT = "left_out";

    private PhotoStore() {}

    static File dir(Context context) {
        File base = context.getExternalFilesDir(null);
        return base == null ? null : new File(base, DIR);
    }

    /** All photos, newest name last; names from add_photos.sh start with the date they were added. */
    static List<File> all(Context context) {
        List<File> out = new ArrayList<>();
        File d = dir(context);
        File[] files = d == null ? null : d.listFiles();
        if (files == null) return out;
        Arrays.sort(files);
        for (File f : files) {
            String n = f.getName().toLowerCase(Locale.ROOT);
            if (f.isFile() && f.length() > 0 && (n.endsWith(".jpg") || n.endsWith(".jpeg") || n.endsWith(".png") || n.endsWith(".webp"))) {
                out.add(f);
            }
        }
        return out;
    }

    static List<File> selected(Context context) {
        Set<String> out = leftOut(context);
        List<File> list = new ArrayList<>();
        for (File f : all(context)) if (!out.contains(f.getName())) list.add(f);
        return list;
    }

    static boolean isSelected(Context context, File f) {
        return !leftOut(context).contains(f.getName());
    }

    static void setSelected(Context context, File f, boolean selected) {
        Set<String> out = new HashSet<>(leftOut(context));
        if (selected) out.remove(f.getName()); else out.add(f.getName());
        prefs(context).edit().putStringSet(LEFT_OUT, out).apply();
    }

    private static Set<String> leftOut(Context context) {
        return prefs(context).getStringSet(LEFT_OUT, new HashSet<>());
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Decodes {@code f} at no more than about {@code maxW} x {@code maxH}, or null if it can't be read. */
    static Bitmap decode(File f, int maxW, int maxH) {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(f.getPath(), o);
        if (o.outWidth <= 0 || o.outHeight <= 0) return null;
        int sample = 1;
        while (o.outWidth / (sample * 2) >= maxW && o.outHeight / (sample * 2) >= maxH) sample *= 2;
        BitmapFactory.Options d = new BitmapFactory.Options();
        d.inSampleSize = sample;
        d.inPreferredConfig = Bitmap.Config.RGB_565;   // half the memory of ARGB on a 1 GB TV
        return BitmapFactory.decodeFile(f.getPath(), d);
    }
}
