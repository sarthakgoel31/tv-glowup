package cv.sarthakgoel.tvhome;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextClock;
import android.widget.TextView;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The family-photo slideshow shared by the screensaver (PhotoDream) and Family Photos' "Play" button. Two image
 * views take turns: the next photo decodes in the background, fades in over the last one and zooms in slowly
 * for its 30 seconds. A small clock sits in the bottom corner. At most two screen-size RGB_565 bitmaps are held.
 */
final class PhotoSlideshow extends FrameLayout {
    static final long SHOW_MS = 30_000L;
    private static final long FADE_MS = 1500L;
    private static final float ZOOM = 1.08f;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService decoder = Executors.newSingleThreadExecutor();
    private final ImageView[] views = new ImageView[2];
    private final android.animation.ObjectAnimator[] zooms = new android.animation.ObjectAnimator[2];
    private final TextView empty;
    private final int width, height;
    private List<File> order = new ArrayList<>();
    private int index = -1, front = 0;
    private boolean running;

    private final Runnable next = this::showNext;

    PhotoSlideshow(Context context) {
        super(context);
        setBackgroundColor(Color.BLACK);
        DisplayMetrics m = context.getResources().getDisplayMetrics();
        width = m.widthPixels;
        height = m.heightPixels;
        // The two photos live in their own layer, so swapping them never moves the clock under a photo.
        FrameLayout stage = new FrameLayout(context);
        addView(stage, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));
        for (int i = 0; i < 2; i++) {
            ImageView v = new ImageView(context);
            v.setScaleType(ImageView.ScaleType.CENTER_CROP);
            v.setAlpha(0f);
            stage.addView(v, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));
            views[i] = v;
        }
        // Soft shade behind the clock so it reads over a bright photo.
        View shade = new View(context);
        shade.setBackground(new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.BOTTOM_TOP,
                new int[]{0x99000000, 0x00000000}));
        addView(shade, new LayoutParams(LayoutParams.MATCH_PARENT, dp(220), Gravity.BOTTOM));

        LinearLayout clock = new LinearLayout(context);
        clock.setOrientation(LinearLayout.VERTICAL);
        Typeface light = getResources().getFont(R.font.outfit_light);
        TextClock time = new TextClock(context);
        time.setFormat12Hour("h:mm");
        time.setFormat24Hour("HH:mm");
        time.setTextColor(0xF2FFFFFF);
        time.setTextSize(TypedValue.COMPLEX_UNIT_SP, 44);
        time.setTypeface(light);
        time.setShadowLayer(dp(6), 0, dp(1), 0x80000000);
        TextClock date = new TextClock(context);
        date.setFormat12Hour("EEEE d MMMM");
        date.setFormat24Hour("EEEE d MMMM");
        date.setTextColor(0xCCFFFFFF);
        date.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        date.setTypeface(light);
        date.setLetterSpacing(0.08f);
        date.setShadowLayer(dp(4), 0, dp(1), 0x80000000);
        clock.addView(time);
        clock.addView(date);
        LayoutParams lp = new LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.WRAP_CONTENT, Gravity.BOTTOM | Gravity.START);
        lp.setMargins(dp(48), 0, 0, dp(36));
        addView(clock, lp);

        empty = new TextView(context);
        empty.setText(R.string.photos_empty);
        empty.setTextColor(0xCCFFFFFF);
        empty.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        empty.setTypeface(light);
        empty.setGravity(Gravity.CENTER);
        empty.setVisibility(GONE);
        addView(empty, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));
    }

    private int dp(float v) {
        return (int) (v * getResources().getDisplayMetrics().density);
    }

    void start(List<File> photos) {
        running = true;
        order = new ArrayList<>(photos);
        Collections.shuffle(order);
        empty.setVisibility(order.isEmpty() ? VISIBLE : GONE);
        if (!order.isEmpty()) showNext();
    }

    void stop() {
        running = false;
        handler.removeCallbacksAndMessages(null);
        for (ImageView v : views) v.animate().cancel();
        for (android.animation.ObjectAnimator z : zooms) if (z != null) z.cancel();
    }

    void release() {
        stop();
        decoder.shutdownNow();
        for (ImageView v : views) v.setImageDrawable(null);
    }

    private void showNext() {
        if (!running || order.isEmpty()) return;
        index = (index + 1) % order.size();
        File f = order.get(index);
        decoder.execute(() -> {
            Bitmap b = PhotoStore.decode(f, width, height);
            handler.post(() -> {
                if (!running) return;
                if (b == null) { handler.post(next); return; }   // unreadable file: skip it
                ImageView in = views[1 - front], out = views[front];
                in.setImageBitmap(b);
                in.setScaleX(1f);
                in.setScaleY(1f);
                in.bringToFront();
                in.animate().alpha(1f).setDuration(FADE_MS).withEndAction(() -> {
                    out.setAlpha(0f);
                    out.setImageDrawable(null);   // free the old bitmap before the next decode
                }).start();
                // The slow zoom runs on its own animator: sharing the fade's would stretch the fade to 30 s.
                int slot = 1 - front;
                if (zooms[slot] != null) zooms[slot].cancel();
                zooms[slot] = android.animation.ObjectAnimator.ofPropertyValuesHolder(in,
                        android.animation.PropertyValuesHolder.ofFloat(View.SCALE_X, 1f, ZOOM),
                        android.animation.PropertyValuesHolder.ofFloat(View.SCALE_Y, 1f, ZOOM));
                zooms[slot].setDuration(SHOW_MS + FADE_MS);
                zooms[slot].setInterpolator(new android.view.animation.LinearInterpolator());
                zooms[slot].start();
                front = 1 - front;
                if (order.size() > 1) handler.postDelayed(next, SHOW_MS);
            });
        });
    }
}
