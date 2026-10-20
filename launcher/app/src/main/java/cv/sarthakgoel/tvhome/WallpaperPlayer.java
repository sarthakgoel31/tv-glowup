package cv.sarthakgoel.tvhome;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Displays and rotates a theme's local wallpaper images while Home is visible. */
final class WallpaperPlayer {
    private final FrameLayout root;
    private final ImageView image;
    private final List<File> files;
    private final long interval;
    private final SharedPreferences preferences;
    private final ExecutorService decoder = Executors.newSingleThreadExecutor();
    private final Random random = new Random();
    private final int width;
    private final int height;
    private boolean active;
    private boolean closed;
    private boolean loading;
    private String displayed = "";
    /** Ambient picture shown instead of the theme's (weather and time of day), or null for the theme's own. */
    private File override;
    /** The picture fading in over {@link #image} during a crossfade; empty otherwise. At most two bitmaps live. */
    private final ImageView front;
    private final boolean enabled;
    private static final long FADE_MS = 800;

    WallpaperPlayer(Context context, FrameLayout root, Config config) {
        this.root = root;
        files = new ArrayList<>(config.wallpapers);
        interval = config.wallpaperRotationMinutes * 60_000L;
        preferences = context.getSharedPreferences("wallpaper_rotation", Context.MODE_PRIVATE);
        DisplayMetrics metrics = context.getResources().getDisplayMetrics();
        width = metrics.widthPixels;
        height = metrics.heightPixels;
        image = new ImageView(context);
        image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        image.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        front = new ImageView(context);
        front.setScaleType(ImageView.ScaleType.CENTER_CROP);
        front.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        front.setVisibility(View.GONE);
        enabled = config.wallpaperEnabled;
        if (config.wallpaperEnabled && !files.isEmpty()) {
            root.addView(image, 0, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            root.addView(front, 1, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            // No shade layer at all when the theme doesn't dim: a full-screen view is overdraw on 1 GB TVs.
            if (config.wallpaperDim > 0) {
                View shade = new View(context);
                shade.setBackgroundColor((config.wallpaperDim * 255 / 100) << 24);
                shade.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
                root.addView(shade, 2, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            }
            showFirst();
        }
    }

    /**
     * The picture Home opens with is decoded right here, on the main thread, as the single wallpaper always was:
     * Home's first frame already has it instead of drawing the plain colour and the picture popping in later.
     * Only the later changes of a rotation decode in the background.
     */
    private void showFirst() {
        String previous = preferences.getString("image", "");
        File first = WallpaperRotation.find(files, previous);
        if (first == null) first = WallpaperRotation.pick(files, previous, random);
        while (first != null) {
            Bitmap bitmap = decode(first);
            if (bitmap != null) {
                image.setImageBitmap(bitmap);
                displayed = first.getName();
                if (!displayed.equals(previous)) {
                    preferences.edit().putString("image", displayed)
                            .putLong("changed", System.currentTimeMillis()).apply();
                }
                return;
            }
            files.remove(first);   // unreadable or over 4K: try another, or keep the plain colour
            first = WallpaperRotation.pick(files, previous, random);
        }
    }

    void start() {
        active = true;
        update();
    }

    void stop() {
        active = false;
    }

    void close() {
        active = false;
        closed = true;
        decoder.shutdownNow();
    }

    /**
     * Shows {@code file} (an ambient picture) instead of the theme's wallpaper, crossfading to it; null goes
     * back to the theme's. Ignored when the theme has no wallpaper or turned it off.
     */
    void setOverride(File file) {
        if (!enabled || files.isEmpty()) return;
        if (file == null ? override == null : file.equals(override)) return;
        override = file;
        update();
    }

    /** Whether an ambient picture is (being) shown in place of the theme's. */
    boolean overridden() {
        return override != null;
    }

    void update() {
        if (!active || closed || loading || files.isEmpty()) return;
        if (override != null) {
            String key = "ambient:" + override.getPath();
            if (!key.equals(displayed)) swap(override, key, false);
            return;
        }
        String previous = preferences.getString("image", "");
        File selected = WallpaperRotation.find(files, previous);
        long changed = preferences.getLong("changed", 0);
        if (selected == null || WallpaperRotation.due(changed, System.currentTimeMillis(), interval)) {
            selected = WallpaperRotation.pick(files, previous, random);
        }
        if (selected == null || selected.getName().equals(displayed)) return;
        swap(selected, selected.getName(), true);
    }

    /** Decodes {@code next} off the main thread, then crossfades to it. {@code rotation}: a theme image. */
    private void swap(File next, String key, boolean rotation) {
        loading = true;
        decoder.execute(() -> {
            Bitmap bitmap = decode(next);
            root.post(() -> {
                loading = false;
                if (closed || !active) {
                    if (bitmap != null) bitmap.recycle();
                    return;
                }
                if (bitmap == null) {
                    Log.w("TvHome.Wallpaper", "Skipping unreadable image: " + next.getName());
                    if (rotation) files.remove(next);
                    else if (next.equals(override)) override = null;   // a broken ambient: back to the theme's
                    update();
                    return;
                }
                // a newer choice arrived while this one decoded: drop it and fetch that one instead
                boolean wanted = override != null ? key.equals("ambient:" + override.getPath()) : rotation;
                if (!wanted) {
                    bitmap.recycle();
                    update();
                    return;
                }
                crossfade(bitmap);
                displayed = key;
                if (rotation) {
                    String previous = preferences.getString("image", "");
                    long changed = preferences.getLong("changed", 0);
                    if (!displayed.equals(previous) || changed == 0) {
                        preferences.edit().putString("image", displayed)
                                .putLong("changed", System.currentTimeMillis()).apply();
                    }
                }
            });
        });
    }

    /** Fades {@code bitmap} in over the current picture, then makes it the picture: two bitmaps at most. */
    private void crossfade(Bitmap bitmap) {
        front.animate().cancel();
        if (front.getVisibility() == View.VISIBLE && front.getDrawable() != null) {
            image.setImageDrawable(front.getDrawable());   // a fade cut short: keep where it got to
        }
        if (image.getDrawable() == null || !image.isAttachedToWindow() || !front.isAttachedToWindow()) {
            image.setImageBitmap(bitmap);
            return;
        }
        front.setImageBitmap(bitmap);
        front.setAlpha(0f);
        front.setVisibility(View.VISIBLE);
        front.animate().alpha(1f).setDuration(FADE_MS).withEndAction(() -> {
            image.setImageBitmap(bitmap);      // the old bitmap is dropped here
            front.setVisibility(View.GONE);
            front.setImageDrawable(null);
        }).start();
    }

    private Bitmap decode(File file) {
        try {
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(file.getPath(), options);
            int width = options.outWidth, height = options.outHeight;
            if (width <= 0 || height <= 0) return null;
            int sample = WallpaperSize.sampleSize(width, height, this.width, this.height);
            if (!WallpaperSize.accepted(width / sample, height / sample)) return null;
            options.inJustDecodeBounds = false;
            options.inSampleSize = sample;
            int[] scale = WallpaperSize.coverScale(width / sample, height / sample, this.width, this.height);
            if (scale != null) {
                options.inScaled = true;
                options.inDensity = scale[0];
                options.inTargetDensity = scale[1];
            }
            options.inPreferredConfig = Bitmap.Config.RGB_565;
            return BitmapFactory.decodeFile(file.getPath(), options);
        } catch (Exception | OutOfMemoryError failure) {
            return null;
        }
    }
}
