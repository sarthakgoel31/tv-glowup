package cv.sarthakgoel.tvhome;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.Outline;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewOutlineProvider;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import java.io.File;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Family Photos: every photo on the TV as a grid. OK on a photo puts it in or takes it out of the screensaver
 * (a gold tick means in). "Play" shows the slideshow now. Photos are added from a computer with add_photos.sh.
 */
public class PhotosActivity extends Activity {
    private static final int COLUMNS = 5;
    private static final int GOLD = 0xFFFFB23C;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService decoder = Executors.newFixedThreadPool(2);
    private final LruCache<String, Bitmap> thumbs = new LruCache<String, Bitmap>(12 * 1024 * 1024) {
        @Override
        protected int sizeOf(String key, Bitmap value) {
            return value.getByteCount();
        }
    };
    private List<File> photos;
    private TextView subtitle;
    private FrameLayout root;
    private PhotoSlideshow show;
    private float density;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        density = getResources().getDisplayMetrics().density;
        Typeface light = getResources().getFont(R.font.outfit_light);
        Typeface medium = getResources().getFont(R.font.outfit_medium);
        photos = PhotoStore.all(this);

        root = new FrameLayout(this);
        root.setBackgroundColor(0xFF070A14);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(56), dp(36), dp(56), 0);
        root.addView(col, new FrameLayout.LayoutParams(-1, -1));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout titles = new LinearLayout(this);
        titles.setOrientation(LinearLayout.VERTICAL);
        TextView title = text(getString(R.string.photos_title), 34, Color.WHITE, light);
        subtitle = text("", 14, 0xB3FFFFFF, light);
        subtitle.setLetterSpacing(0.04f);
        titles.addView(title);
        titles.addView(subtitle);
        header.addView(titles, new LinearLayout.LayoutParams(0, -2, 1f));
        TextView play = text(getString(R.string.photos_play), 16, Color.WHITE, medium);
        play.setFocusable(true);
        play.setPadding(dp(22), dp(10), dp(22), dp(10));
        play.setBackground(pill(false));
        play.setOnFocusChangeListener((v, f) -> v.setBackground(pill(f)));
        play.setOnClickListener(v -> startShow());
        header.addView(play);
        col.addView(header);

        RecyclerView grid = new RecyclerView(this);
        grid.setLayoutManager(new GridLayoutManager(this, COLUMNS));
        grid.setClipToPadding(false);
        grid.setPadding(0, dp(20), 0, dp(40));
        grid.setAdapter(new Adapter());
        col.addView(grid, new LinearLayout.LayoutParams(-1, 0, 1f));

        if (photos.isEmpty()) {
            TextView none = text(getString(R.string.photos_empty), 18, 0xCCFFFFFF, light);
            none.setGravity(Gravity.CENTER);
            root.addView(none, new FrameLayout.LayoutParams(-1, -1));
            play.requestFocus();
        }
        setContentView(root);
        updateSubtitle();
    }

    private void updateSubtitle() {
        int in = PhotoStore.selected(this).size();
        subtitle.setText(getString(R.string.photos_subtitle, in, photos.size()));
    }

    private void startShow() {
        if (show != null) return;
        show = new PhotoSlideshow(this);
        root.addView(show, new FrameLayout.LayoutParams(-1, -1));
        show.start(PhotoStore.selected(this));
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        // Any key ends the preview slideshow, as it would end the screensaver.
        if (show != null && event.getAction() == KeyEvent.ACTION_UP) {
            show.release();
            root.removeView(show);
            show = null;
            return true;
        }
        if (show != null) return true;
        return super.dispatchKeyEvent(event);
    }

    @Override
    protected void onStop() {
        if (show != null) { show.release(); root.removeView(show); show = null; }
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        decoder.shutdownNow();
        thumbs.evictAll();
        super.onDestroy();
    }

    private TextView text(String s, float sp, int color, Typeface tf) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        t.setTypeface(tf);
        return t;
    }

    private GradientDrawable pill(boolean focused) {
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(30));
        g.setColor(focused ? 0x40FFFFFF : 0x1FFFFFFF);
        g.setStroke(dp(focused ? 2 : 1), focused ? GOLD : 0x33FFFFFF);
        return g;
    }

    private int dp(float v) {
        return (int) (v * density);
    }

    private final class Holder extends RecyclerView.ViewHolder {
        final FrameLayout card;
        final ImageView image;
        final TextView tick;
        File file;

        Holder(FrameLayout card, ImageView image, TextView tick) {
            super(card);
            this.card = card;
            this.image = image;
            this.tick = tick;
        }
    }

    private final class Adapter extends RecyclerView.Adapter<Holder> {
        @Override
        public Holder onCreateViewHolder(ViewGroup parent, int viewType) {
            int w = (parent.getWidth() > 0 ? parent.getWidth() : getResources().getDisplayMetrics().widthPixels - dp(112)) / COLUMNS;
            FrameLayout card = new FrameLayout(PhotosActivity.this);
            RecyclerView.LayoutParams lp = new RecyclerView.LayoutParams(w, w * 9 / 16 + dp(16));
            card.setLayoutParams(lp);
            card.setFocusable(true);
            card.setPadding(dp(8), dp(8), dp(8), dp(8));
            card.setClipToPadding(false);
            ImageView image = new ImageView(PhotosActivity.this);
            image.setScaleType(ImageView.ScaleType.CENTER_CROP);
            image.setBackgroundColor(0xFF1A1F2E);
            image.setOutlineProvider(new ViewOutlineProvider() {
                @Override
                public void getOutline(View view, Outline outline) {
                    outline.setRoundRect(0, 0, view.getWidth(), view.getHeight(), dp(10));
                }
            });
            image.setClipToOutline(true);
            card.addView(image, new FrameLayout.LayoutParams(-1, -1));
            TextView tick = new TextView(PhotosActivity.this);
            tick.setText("✓");
            tick.setTextColor(0xFF1A1206);
            tick.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            tick.setGravity(Gravity.CENTER);
            GradientDrawable dot = new GradientDrawable();
            dot.setShape(GradientDrawable.OVAL);
            dot.setColor(GOLD);
            tick.setBackground(dot);
            FrameLayout.LayoutParams tp = new FrameLayout.LayoutParams(dp(26), dp(26), Gravity.TOP | Gravity.END);
            tp.setMargins(0, dp(8), dp(8), 0);
            card.addView(tick, tp);
            Holder h = new Holder(card, image, tick);
            card.setOnFocusChangeListener((v, f) -> {
                v.animate().scaleX(f ? 1.08f : 1f).scaleY(f ? 1.08f : 1f).setDuration(150).start();
                v.setZ(f ? 1 : 0);
                image.setForeground(f ? ring() : null);
            });
            card.setOnClickListener(v -> {
                if (h.file == null) return;
                boolean now = !PhotoStore.isSelected(PhotosActivity.this, h.file);
                PhotoStore.setSelected(PhotosActivity.this, h.file, now);
                bindState(h);
                updateSubtitle();
            });
            return h;
        }

        @Override
        public void onBindViewHolder(Holder h, int position) {
            File f = photos.get(position);
            h.file = f;
            bindState(h);
            Bitmap cached = thumbs.get(f.getPath());
            h.image.setImageBitmap(cached);
            if (cached == null) {
                decoder.execute(() -> {
                    Bitmap b = PhotoStore.decode(f, 400, 225);
                    if (b == null) return;
                    handler.post(() -> {
                        thumbs.put(f.getPath(), b);
                        if (f.equals(h.file)) h.image.setImageBitmap(b);
                    });
                });
            }
            if (position == 0 && !h.card.hasFocus()) h.card.post(h.card::requestFocus);
        }

        @Override
        public int getItemCount() {
            return photos.size();
        }
    }

    private void bindState(Holder h) {
        boolean in = PhotoStore.isSelected(this, h.file);
        h.tick.setVisibility(in ? View.VISIBLE : View.INVISIBLE);
        h.image.setAlpha(in ? 1f : 0.35f);
    }

    private GradientDrawable ring() {
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(10));
        g.setStroke(dp(3), Color.WHITE);
        return g;
    }
}
