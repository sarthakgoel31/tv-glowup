package cv.sarthakgoel.tvhome;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.os.SystemClock;
import android.view.View;

import java.util.Random;

/**
 * A transparent full-screen overlay that plays one short festival animation on a Home press (the marigold
 * shower has its own {@link PetalShowerView}):
 * <ul>
 * <li>{@code snow}: soft white flakes at three depths drifting down with a slight sway, the near ones larger
 * and out of focus;</li>
 * <li>{@code colors}: puffs of gulal (magenta, saffron, green, blue, yellow) blooming outward and fading, with
 * fine specks thrown out of each;</li>
 * <li>{@code sparkles}: four gold and champagne firework bursts, sparks streaking out under drag and gravity,
 * and a few twinkles;</li>
 * <li>{@code embers}: warm sparks rising from the bottom over a faint glow, cooling from yellow to red;</li>
 * <li>{@code tricolour}: saffron, white and green paper confetti falling and flipping gently.</li>
 * </ul>
 * At most {@link #MAX} particles, everything finishes within the duration, then the callback runs on the main
 * thread. All paints, shaders and particle arrays are made up front: onDraw allocates nothing. The view takes no
 * focus, clicks or accessibility.
 */
public final class FestiveEffectView extends View {

    static final int MAX = 70;
    private static final double TAU = 2 * Math.PI;

    private static final int[] GULAL = {0xFFE8408F, 0xFFFF9A2E, 0xFF38C46A, 0xFF3F7DFF, 0xFFFFD43F};
    private static final int[] GOLDS = {0xFFFFD27A, 0xFFF6E3B4, 0xFFFFF3DA, 0xFFFFBF5A};
    private static final int[] FLAG = {0xFFFF9933, 0xFFF7F6F0, 0xFF1F9E3E};
    private static final int EMBER_HOT = 0xFFFFE9B0, EMBER_WARM = 0xFFFFA238, EMBER_COOL = 0xFFD9472A;

    private final String effect;
    private final float dp;
    private final Random rnd = new Random();

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint haze = new Paint();
    private final Paint streak = new Paint(Paint.ANTI_ALIAS_FLAG);
    /** Unit-radius radial gradients, drawn by scaling the canvas so one shader serves every size. */
    private final Shader[] shaders;

    // particle state: positions in px, times in seconds
    private int count;
    private final float[] x0 = new float[MAX], y0 = new float[MAX], vx = new float[MAX], vy = new float[MAX],
            size = new float[MAX], delay = new float[MAX], life = new float[MAX], amp = new float[MAX],
            freq = new float[MAX], phase = new float[MAX], rot0 = new float[MAX], spin = new float[MAX],
            alpha = new float[MAX];
    private final int[] color = new int[MAX], kind = new int[MAX];

    // sparkles: burst centres and start times
    private static final int BURSTS = 4;
    private final float[] burstX = new float[BURSTS], burstY = new float[BURSTS], burstT = new float[BURSTS];

    private boolean playing;
    private long start, duration;
    private Runnable onDone;
    private final Runnable finish = this::finish;

    FestiveEffectView(Context context, String effect) {
        super(context);
        this.effect = effect;
        dp = context.getResources().getDisplayMetrics().density;
        setFocusable(false);
        setClickable(false);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        setWillNotDraw(false);

        fill.setStyle(Paint.Style.FILL);

        switch (effect) {
            case Festival.EFFECT_SNOW:
                // a crisp flake and an out-of-focus one
                shaders = new Shader[]{
                        radial(0xFFFFFFFF, 0xE6FFFFFF, 0.42f),
                        radial(0xB3FFFFFF, 0x59FFFFFF, 0.4f)};
                break;
            case Festival.EFFECT_COLORS:
                shaders = new Shader[GULAL.length];
                for (int i = 0; i < GULAL.length; i++) {
                    int c = GULAL[i] & 0xFFFFFF;
                    shaders[i] = radial(0xF0000000 | c, 0x80000000 | c, 0.45f);
                }
                break;
            case Festival.EFFECT_SPARKLES:
                // [0] the burst flash and twinkle rays, [1..] a comet streak per spark colour: clear tail, lit head
                shaders = new Shader[1 + GOLDS.length];
                shaders[0] = radial(0xFFFFF1D0, 0x55FFC86A, 0.3f);
                for (int i = 0; i < GOLDS.length; i++) {
                    int c = GOLDS[i] & 0xFFFFFF;
                    shaders[1 + i] = new LinearGradient(0f, 0f, 1f, 0f, new int[]{c, 0x8C000000 | c, 0xFF000000 | c},
                            new float[]{0f, 0.7f, 1f}, Shader.TileMode.CLAMP);
                }
                break;
            case Festival.EFFECT_EMBERS:
                shaders = new Shader[]{radial(0xCCFF9A3A, 0x33FF6A1A, 0.35f)};
                break;
            default:
                shaders = new Shader[0];
                break;
        }
    }

    /** A gradient of radius 1 at the origin: {@code inner} at the centre, {@code mid} at {@code at}, clear at 1. */
    private static Shader radial(int inner, int mid, float at) {
        return new RadialGradient(0f, 0f, 1f, new int[]{inner, mid, mid & 0x00FFFFFF},
                new float[]{0f, at, 1f}, Shader.TileMode.CLAMP);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        if (Festival.EFFECT_EMBERS.equals(effect) && h > 0) {
            haze.setShader(new LinearGradient(0f, h, 0f, h * 0.72f, 0x40FF7A1E, 0x00FF7A1E, Shader.TileMode.CLAMP));
        }
    }

    /** Plays the effect for {@code durationMs} on a view already laid out over the screen, then runs {@code done}. */
    void play(long durationMs, Runnable done) {
        if (playing) {
            removeCallbacks(finish);
            finish();
        }
        duration = Math.max(1, durationMs);
        onDone = done;
        if (getWidth() == 0) {
            // not laid out yet: start on the first layout pass
            post(() -> begin());
        } else {
            begin();
        }
    }

    private void begin() {
        float w = Math.max(1, getWidth()), h = Math.max(1, getHeight());
        float secs = duration / 1000f;
        switch (effect) {
            case Festival.EFFECT_SNOW: initSnow(w, h, secs); break;
            case Festival.EFFECT_COLORS: initColors(w, h, secs); break;
            case Festival.EFFECT_SPARKLES: initSparkles(w, h, secs); break;
            case Festival.EFFECT_EMBERS: initEmbers(w, h, secs); break;
            case Festival.EFFECT_TRICOLOUR: initTricolour(w, h, secs); break;
            default: count = 0; break;
        }
        playing = true;
        start = SystemClock.uptimeMillis();
        postDelayed(finish, duration);
        postInvalidateOnAnimation();
    }

    private void finish() {
        if (!playing) return;
        playing = false;
        invalidate();
        Runnable done = onDone;
        onDone = null;
        if (done != null) done.run();
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        if (playing) {
            removeCallbacks(finish);
            finish();
        }
    }

    // ---------------------------------------------------------------- set-up

    /** A start delay and a life that ends before the effect does. */
    private void timing(int i, float secs, float maxDelay, float minLife, float maxLife) {
        delay[i] = rnd.nextFloat() * maxDelay * secs;
        float room = secs * 0.98f - delay[i];
        life[i] = Math.min(room, (minLife + rnd.nextFloat() * (maxLife - minLife)) * secs);
    }

    private void initSnow(float w, float h, float secs) {
        count = 56;
        for (int i = 0; i < count; i++) {
            float d = rnd.nextFloat();
            d = d * d;                                         // mostly far, small flakes
            boolean bokeh = i % 9 == 0;                        // a few large, soft ones close to the glass
            if (bokeh) d = 0.85f + 0.15f * rnd.nextFloat();
            kind[i] = bokeh ? 1 : 0;
            size[i] = (bokeh ? 9f + 6f * rnd.nextFloat() : 3f + 4.5f * d) * dp;     // gradient radius, the flake is ~half
            x0[i] = (i + rnd.nextFloat()) / count * w;
            y0[i] = (-0.06f + 0.62f * (float) Math.pow(rnd.nextFloat(), 1.4)) * h;
            vy[i] = (26f + 75f * d) * dp;
            vx[i] = (4f + 6f * rnd.nextFloat()) * dp;         // a light breeze
            amp[i] = (5f + 13f * rnd.nextFloat()) * dp;
            freq[i] = 0.22f + 0.3f * rnd.nextFloat();
            phase[i] = rnd.nextFloat() * (float) TAU;
            alpha[i] = bokeh ? 0.36f + 0.14f * rnd.nextFloat() : 1f - 0.25f * d;
            timing(i, secs, 0.3f, 0.6f, 0.95f);
        }
        shuffle(x0, count);
    }

    private void initColors(float w, float h, float secs) {
        // six puffs, three soft blobs each, spread over a loose diagonal arrangement
        float[][] anchors = {{0.12f, 0.36f}, {0.30f, 0.56f}, {0.47f, 0.30f}, {0.64f, 0.52f}, {0.82f, 0.28f},
                {0.92f, 0.56f}};
        int[] order = {0, 1, 2, 3, 4, rnd.nextInt(GULAL.length)};
        shuffle(order);
        int puffs = anchors.length;
        int n = 0;
        for (int p = 0; p < puffs; p++) {
            float cx = (anchors[p][0] + (rnd.nextFloat() - 0.5f) * 0.06f) * w;
            float cy = (anchors[p][1] + (rnd.nextFloat() - 0.5f) * 0.08f) * h;
            float r = (85f + 50f * rnd.nextFloat()) * dp;
            float t0 = (p * 0.11f + rnd.nextFloat() * 0.06f) * secs;
            int c = order[p];
            for (int b = 0; b < 3; b++, n++) {
                kind[n] = 0;
                double a = rnd.nextFloat() * TAU;
                float off = b == 0 ? 0f : 0.3f + 0.25f * rnd.nextFloat();
                x0[n] = cx;
                y0[n] = cy;
                vx[n] = (float) Math.cos(a) * off * r;           // where this blob's centre drifts to
                vy[n] = (float) Math.sin(a) * off * r;
                size[n] = r * (b == 0 ? 1f : 0.6f + 0.25f * rnd.nextFloat());
                color[n] = c;
                delay[n] = t0 + b * 0.04f * secs;
                life[n] = Math.min(secs * 0.98f - delay[n], (0.6f + 0.1f * rnd.nextFloat()) * secs);
                alpha[n] = b == 0 ? 0.62f : 0.5f;
            }
            for (int s = 0; s < 6; s++, n++) {
                kind[n] = 1;
                double a = rnd.nextFloat() * TAU;
                float v = (170f + 260f * rnd.nextFloat()) * dp;
                x0[n] = cx;
                y0[n] = cy;
                vx[n] = (float) Math.cos(a) * v;
                vy[n] = (float) Math.sin(a) * v;
                size[n] = (1.1f + 1.3f * rnd.nextFloat()) * dp;
                color[n] = c;
                delay[n] = t0 + 0.02f * secs;
                life[n] = Math.min(secs * 0.98f - delay[n], (0.32f + 0.14f * rnd.nextFloat()) * secs);
                alpha[n] = 0.9f;
            }
        }
        count = n;                                              // 6 x (3 + 6) = 54
    }

    private void initSparkles(float w, float h, float secs) {
        float[] xs = {0.22f, 0.5f, 0.78f, 0.36f};
        float[] ys = {0.28f, 0.18f, 0.32f, 0.44f};
        int[] order = {0, 1, 2, 3};
        shuffle(order);
        for (int b = 0; b < BURSTS; b++) {
            burstX[b] = (xs[order[b]] + (rnd.nextFloat() - 0.5f) * 0.08f) * w;
            burstY[b] = (ys[order[b]] + (rnd.nextFloat() - 0.5f) * 0.08f) * h;
            burstT[b] = (0.02f + b * 0.14f + rnd.nextFloat() * 0.03f) * secs;
        }
        int perBurst = 14, n = 0;
        for (int b = 0; b < BURSTS; b++) {
            float spread = 0.85f + 0.3f * rnd.nextFloat();
            float turn = rnd.nextFloat() * (float) TAU;
            for (int s = 0; s < perBurst; s++, n++) {
                kind[n] = b;                                   // which burst
                double a = turn + TAU * (s + 0.3f * rnd.nextFloat()) / perBurst;
                float v = (210f + 120f * rnd.nextFloat()) * spread * dp;
                vx[n] = (float) Math.cos(a) * v;
                vy[n] = (float) Math.sin(a) * v;
                color[n] = rnd.nextInt(GOLDS.length);
                delay[n] = burstT[b];
                life[n] = Math.min(secs * 0.98f - delay[n], (0.4f + 0.12f * rnd.nextFloat()) * secs);
                size[n] = (1.3f + 0.5f * rnd.nextFloat()) * dp;
                phase[n] = rnd.nextFloat() * (float) TAU;
            }
        }
        for (int t = 0; t < 10; t++, n++) {
            kind[n] = -1;                                      // twinkle
            x0[n] = (0.06f + 0.88f * rnd.nextFloat()) * w;
            y0[n] = (0.06f + 0.6f * rnd.nextFloat()) * h;
            size[n] = (4f + 4f * rnd.nextFloat()) * dp;
            color[n] = GOLDS[2];
            delay[n] = (0.15f + 0.6f * rnd.nextFloat()) * secs;
            life[n] = Math.min(secs * 0.98f - delay[n], (0.18f + 0.08f * rnd.nextFloat()) * secs);
        }
        count = n;                                              // 56 sparks + 10 twinkles
    }

    private void initEmbers(float w, float h, float secs) {
        count = 46;
        for (int i = 0; i < count; i++) {
            x0[i] = (0.03f + 0.94f * (i + rnd.nextFloat()) / count) * w;
            y0[i] = h + (4f + 10f * rnd.nextFloat()) * dp - rnd.nextFloat() * 0.08f * h;
            vy[i] = (95f + 120f * rnd.nextFloat()) * dp;
            vx[i] = (rnd.nextFloat() - 0.35f) * 30f * dp;      // the heat leans a little to the right
            amp[i] = (6f + 14f * rnd.nextFloat()) * dp;
            freq[i] = 0.6f + 0.9f * rnd.nextFloat();
            phase[i] = rnd.nextFloat() * (float) TAU;
            spin[i] = 9f + 8f * rnd.nextFloat();               // flicker, radians per second
            size[i] = (1.6f + 1.8f * rnd.nextFloat()) * dp;
            alpha[i] = 0.75f + 0.25f * rnd.nextFloat();
            timing(i, secs, 0.42f, 0.4f, 0.58f);
        }
        shuffle(x0, count);
    }

    private void initTricolour(float w, float h, float secs) {
        count = 54;
        for (int i = 0; i < count; i++) {
            x0[i] = (i + rnd.nextFloat()) / count * w;
            y0[i] = -(8f + 40f * rnd.nextFloat()) * dp;
            vy[i] = (0.55f + 0.4f * rnd.nextFloat()) * h;      // distance fallen over its life
            amp[i] = (8f + 16f * rnd.nextFloat()) * dp;
            freq[i] = 0.35f + 0.4f * rnd.nextFloat();
            phase[i] = rnd.nextFloat() * (float) TAU;
            rot0[i] = rnd.nextFloat() * 360f;
            spin[i] = (30f + 90f * rnd.nextFloat()) * (rnd.nextBoolean() ? 1f : -1f);
            vx[i] = 0.5f + 0.9f * rnd.nextFloat();             // flip rate, Hz
            alpha[i] = rnd.nextFloat() * (float) TAU;          // flip phase
            size[i] = (7f + 4f * rnd.nextFloat()) * dp;        // length; width is ~0.55 of it
            kind[i] = rnd.nextInt(4) == 0 ? 1 : 0;             // a few slim streamers
            color[i] = FLAG[i % FLAG.length];
            timing(i, secs, 0.34f, 0.6f, 0.66f);
        }
        shuffle(x0, count);
    }

    // ---------------------------------------------------------------- drawing

    @Override
    protected void onDraw(Canvas c) {
        if (!playing) return;
        float t = (SystemClock.uptimeMillis() - start) / 1000f;
        switch (effect) {
            case Festival.EFFECT_SNOW: drawSnow(c, t); break;
            case Festival.EFFECT_COLORS: drawColors(c, t); break;
            case Festival.EFFECT_SPARKLES: drawSparkles(c, t); break;
            case Festival.EFFECT_EMBERS: drawEmbers(c, t); break;
            case Festival.EFFECT_TRICOLOUR: drawTricolour(c, t); break;
            default: break;
        }
        postInvalidateOnAnimation();
    }

    private void drawSnow(Canvas c, float t) {
        for (int i = 0; i < count; i++) {
            float lt = t - delay[i];
            float p = lt / life[i];
            if (p <= 0f || p >= 1f) continue;
            float env = smooth(p / 0.25f) * smooth((1f - p) / 0.4f);
            float x = x0[i] + vx[i] * lt + amp[i] * (float) Math.sin(TAU * freq[i] * lt + phase[i]);
            float y = y0[i] + vy[i] * lt;
            glow.setShader(shaders[kind[i]]);
            glow.setAlpha((int) (255 * alpha[i] * env));
            disc(c, x, y, size[i]);
        }
    }

    private void drawColors(Canvas c, float t) {
        for (int i = 0; i < count; i++) {
            float lt = t - delay[i];
            float p = lt / life[i];
            if (p <= 0f || p >= 1f) continue;
            if (kind[i] == 0) {
                float e = 1f - cube(1f - Math.min(1f, p / 0.7f));          // eases out, like a thrown cloud
                float env = smooth(p / 0.1f) * smooth((1f - p) / 0.75f);
                float r = size[i] * (0.3f + 0.7f * e);
                glow.setShader(shaders[color[i]]);
                glow.setAlpha((int) (255 * alpha[i] * env));
                disc(c, x0[i] + vx[i] * e, y0[i] + vy[i] * e - 10f * dp * p, r);
            } else {
                float f = (1f - (float) Math.exp(-3.2f * lt)) / 3.2f;      // drag
                float x = x0[i] + vx[i] * f;
                float y = y0[i] + vy[i] * f + 40f * dp * lt * lt;
                fill.setShader(null);
                fill.setColor(lift(GULAL[color[i]], 0.15f));
                fill.setAlpha((int) (255 * alpha[i] * smooth(p / 0.08f) * (1f - p)));
                c.drawCircle(x, y, size[i], fill);
            }
        }
    }

    private void drawSparkles(Canvas c, float t) {
        // the flash of each burst
        glow.setShader(shaders[0]);
        for (int b = 0; b < BURSTS; b++) {
            float lt = t - burstT[b];
            if (lt <= 0f || lt > 0.45f) continue;
            float k = lt < 0.06f ? lt / 0.06f : 1f - (lt - 0.06f) / 0.39f;
            glow.setAlpha((int) (150 * k * k));
            disc(c, burstX[b], burstY[b], (26f + 30f * (lt / 0.45f)) * dp);
        }
        final float drag = 2.3f, g = 85f * dp;
        for (int i = 0; i < count; i++) {
            float lt = t - delay[i];
            float p = lt / life[i];
            if (p <= 0f || p >= 1f) continue;
            if (kind[i] < 0) {
                // a twinkle: two soft rays and a point of light, swelling and fading
                float s = (float) Math.sin(Math.PI * p);
                float len = size[i] * s;
                glow.setAlpha((int) (235 * s));
                ray(c, x0[i], y0[i], len, 0.9f * dp);
                ray(c, x0[i], y0[i], 0.9f * dp, len);
                ray(c, x0[i], y0[i], 2.4f * dp * s, 2.4f * dp * s);
                continue;
            }
            int b = kind[i];
            float tail = Math.max(0f, lt - 0.16f);
            float fh = (1f - (float) Math.exp(-drag * lt)) / drag;
            float ft = (1f - (float) Math.exp(-drag * tail)) / drag;
            float hx = burstX[b] + vx[i] * fh, hy = burstY[b] + vy[i] * fh + g / drag * (lt - fh);
            float tx = burstX[b] + vx[i] * ft, ty = burstY[b] + vy[i] * ft + g / drag * (tail - ft);
            float fade = (float) Math.pow(1f - p, 1.3);
            if (p > 0.55f) fade *= 0.65f + 0.35f * (float) Math.sin(38f * lt + phase[i]);   // crackle as it dies
            float dx = hx - tx, dy = hy - ty;
            float len = (float) Math.sqrt(dx * dx + dy * dy);
            if (len > 0.5f) {
                // a comet streak: a rotated rect with a clear-to-lit gradient along it
                streak.setShader(shaders[1 + color[i]]);
                streak.setAlpha((int) (225 * fade));
                c.save();
                c.translate(tx, ty);
                c.rotate((float) Math.toDegrees(Math.atan2(dy, dx)));
                c.scale(len, size[i]);
                c.drawRect(0f, -0.5f, 1f, 0.5f, streak);
                c.restore();
            }
            fill.setShader(null);
            fill.setColor(0xFFFFF8E8);
            fill.setAlpha((int) (255 * fade));
            c.drawCircle(hx, hy, size[i] * 0.7f, fill);
        }
    }

    /** The glow shader stretched to an ellipse of radii (rx, ry) at (x, y): a soft ray of light. */
    private void ray(Canvas c, float x, float y, float rx, float ry) {
        if (rx < 0.3f || ry < 0.3f) return;
        c.save();
        c.translate(x, y);
        c.scale(rx, ry);
        c.drawCircle(0f, 0f, 1f, glow);
        c.restore();
    }

    private void drawEmbers(Canvas c, float t) {
        float T = t / (duration / 1000f);
        float hazeA = (float) Math.sin(Math.PI * Math.min(1f, Math.max(0f, T)));
        haze.setAlpha((int) (255 * 0.75f * hazeA));
        c.drawRect(0f, getHeight() * 0.72f, getWidth(), getHeight(), haze);
        glow.setShader(shaders[0]);
        fill.setShader(null);
        for (int i = 0; i < count; i++) {
            float lt = t - delay[i];
            float p = lt / life[i];
            if (p <= 0f || p >= 1f) continue;
            float y = y0[i] - vy[i] * lt * (1f - 0.3f * p);                   // slows as it cools
            float x = x0[i] + vx[i] * lt + amp[i] * (float) Math.sin(TAU * freq[i] * lt + phase[i]) * p;
            float flicker = 0.72f + 0.28f * (float) Math.sin(spin[i] * lt + phase[i]);
            float env = smooth(p / 0.12f) * (float) Math.pow(1f - p, 1.2) * flicker * alpha[i];
            float r = size[i] * (1f - 0.45f * p);
            glow.setAlpha((int) (200 * env));
            disc(c, x, y, r * 4.2f);
            fill.setColor(p < 0.4f ? mix(EMBER_HOT, EMBER_WARM, p / 0.4f) : mix(EMBER_WARM, EMBER_COOL, (p - 0.4f) / 0.6f));
            fill.setAlpha((int) (255 * env));
            c.drawCircle(x, y, r, fill);
        }
    }

    private void drawTricolour(Canvas c, float t) {
        fill.setShader(null);
        for (int i = 0; i < count; i++) {
            float lt = t - delay[i];
            float p = lt / life[i];
            if (p <= 0f || p >= 1f) continue;
            float fall = p * (0.7f + 0.3f * p);                                // drifts in, then settles to speed
            double sway = TAU * freq[i] * lt + phase[i];
            float x = x0[i] + amp[i] * (float) Math.sin(sway);
            float y = y0[i] + vy[i] * fall;
            float angle = rot0[i] + spin[i] * lt + 18f * (float) Math.cos(sway);
            float flip = (float) Math.cos(TAU * vx[i] * lt + alpha[i]);
            float sx = Math.abs(flip) < 0.12f ? (flip < 0f ? -0.12f : 0.12f) : flip;
            float shade = (flip < 0f ? 0.8f : 1f) * (0.82f + 0.18f * Math.abs(flip));
            float a = smooth(p / 0.08f) * (p > 0.72f ? 1f - (p - 0.72f) / 0.28f : 1f);
            fill.setColor(scale(color[i], shade));
            fill.setAlpha((int) (235 * a));
            float len = size[i], half = len * (kind[i] == 1 ? 0.16f : 0.3f);
            c.save();
            c.translate(x, y);
            c.rotate(angle);
            c.scale(sx, 1f);
            c.drawRect(-half, -len * 0.5f, half, len * 0.5f, fill);
            c.restore();
        }
    }

    /** A glow disc of radius {@code r} at (x, y) drawn with {@link #glow}'s unit shader. */
    private void disc(Canvas c, float x, float y, float r) {
        c.save();
        c.translate(x, y);
        c.scale(r, r);
        c.drawCircle(0f, 0f, 1f, glow);
        c.restore();
    }

    // ---------------------------------------------------------------- helpers

    private static float smooth(float v) {
        if (v <= 0f) return 0f;
        if (v >= 1f) return 1f;
        return v * v * (3f - 2f * v);
    }

    private static float cube(float v) {
        return v * v * v;
    }

    private void shuffle(float[] a, int n) {
        for (int i = n - 1; i > 0; i--) {
            int j = rnd.nextInt(i + 1);
            float tmp = a[i];
            a[i] = a[j];
            a[j] = tmp;
        }
    }

    private void shuffle(int[] a) {
        for (int i = a.length - 1; i > 0; i--) {
            int j = rnd.nextInt(i + 1);
            int tmp = a[i];
            a[i] = a[j];
            a[j] = tmp;
        }
    }

    private static int mix(int a, int b, float f) {
        f = Math.max(0f, Math.min(1f, f));
        int r = (int) (((a >> 16) & 0xFF) + (((b >> 16) & 0xFF) - ((a >> 16) & 0xFF)) * f);
        int g = (int) (((a >> 8) & 0xFF) + (((b >> 8) & 0xFF) - ((a >> 8) & 0xFF)) * f);
        int bl = (int) ((a & 0xFF) + ((b & 0xFF) - (a & 0xFF)) * f);
        return 0xFF000000 | (r << 16) | (g << 8) | bl;
    }

    private static int lift(int c, float f) {
        return mix(c, 0xFFFFFFFF, f);
    }

    private static int scale(int c, float f) {
        int r = Math.min(255, (int) (((c >> 16) & 0xFF) * f));
        int g = Math.min(255, (int) (((c >> 8) & 0xFF) * f));
        int b = Math.min(255, (int) ((c & 0xFF) * f));
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }
}
