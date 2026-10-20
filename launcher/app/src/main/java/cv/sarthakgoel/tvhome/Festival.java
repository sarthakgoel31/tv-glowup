package cv.sarthakgoel.tvhome;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Locale;

/**
 * A festive skin set by a theme's config.json: {@code festival}, {@code festival_until}, {@code greeting}
 * and {@code accent_color}. While it is active the pills get festive icons (a diya for the network, a bell
 * for Inputs, a marigold for Settings), the greeting is replaced and the focus glow takes the accent colour.
 * It switches itself off after {@code festival_until}, so nobody has to remember to undo it.
 */
final class Festival {

    /** Home-press animations, the {@link #effect} names. */
    static final String EFFECT_NONE = "none", EFFECT_PETALS = "petals", EFFECT_SNOW = "snow",
            EFFECT_COLORS = "colors", EFFECT_SPARKLES = "sparkles", EFFECT_EMBERS = "embers",
            EFFECT_TRICOLOUR = "tricolour";

    static final Festival NONE = new Festival("", null, "", 0, "", false, EFFECT_NONE);

    /** Warm diya gold, the accent when a theme names a festival but no colour. */
    static final int DEFAULT_ACCENT = 0xFFFFB23C;

    /** Lower-case festival name, or "" for none. */
    final String name;
    /** Last day the skin shows, inclusive; null for no end date. */
    final LocalDate until;
    /** Text that replaces the time-of-day greeting; "" uses the festival's own default. */
    final String greeting;
    /** Focus glow colour as 0xAARRGGBB, or 0 for {@link #DEFAULT_ACCENT}. */
    final int accent;
    /** Theme file festivals/&lt;wallpaper&gt;.jpg shown while active; "" keeps the theme's own wallpaper. */
    final String wallpaper;
    /** A small lit diya before the greeting. */
    final boolean diya;
    /** The animation played on every Home press: one of the EFFECT_* names, {@link #EFFECT_NONE} for none. */
    final String effect;

    private Festival(String name, LocalDate until, String greeting, int accent, String wallpaper,
                     boolean diya, String effect) {
        this.name = name;
        this.until = until;
        this.greeting = greeting;
        this.accent = accent;
        this.wallpaper = wallpaper;
        this.diya = diya;
        this.effect = effect == null ? EFFECT_NONE : effect;
    }

    /**
     * {@code "festival": "auto"}: the occasion on today's date from {@link FestivalCalendar}, or {@link #NONE}
     * on an ordinary day. It ends on its own last day, so Home picks the next one up without a theme push.
     */
    static Festival forDate(LocalDate day) {
        FestivalCalendar.Entry e = FestivalCalendar.on(day);
        if (e == null) return NONE;
        return new Festival(e.id, e.end, e.greeting, e.accent, e.wallpaper, e.diya, e.effect);
    }

    /**
     * Builds the skin from raw config values. Anything malformed turns the skin off rather than leaving a
     * festival on the screen forever: an unreadable end date or an empty name gives {@link #NONE}.
     */
    static Festival parse(String name, String until, String greeting, String accent) {
        String n = name == null ? "" : name.trim().toLowerCase(Locale.ROOT);
        if (n.isEmpty() || n.length() > 40) return NONE;
        if (n.equals("auto")) return forDate(LocalDate.now());
        LocalDate end = null;
        if (until != null && !until.trim().isEmpty()) {
            try {
                end = LocalDate.parse(until.trim());
            } catch (DateTimeParseException e) {
                return NONE;
            }
        }
        String g = greeting == null ? "" : Cards.cleanLabel(greeting, "");
        boolean lamp = n.equals("diwali") || n.equals("dussehra");
        return new Festival(n, end, g, parseColor(accent), n, lamp, lamp ? EFFECT_PETALS : EFFECT_NONE);
    }

    /** Whether the skin shows today. */
    boolean active(LocalDate today) {
        return !name.isEmpty() && (until == null || !today.isAfter(until));
    }

    /** The greeting to show while active, or "" to keep the normal time-of-day greeting. */
    String greetingText() {
        if (!greeting.isEmpty()) return greeting;
        switch (name) {
            case "dussehra":
                return "Happy Dussehra";
            case "diwali":
                return "Happy Diwali";
            default:
                return "";
        }
    }

    /** Whether a Home press plays an animation. */
    boolean hasEffect() {
        return !EFFECT_NONE.equals(effect);
    }

    int accentColor() {
        return accent != 0 ? accent : DEFAULT_ACCENT;
    }

    /** {@code #RRGGBB} to an opaque colour, anything else to 0. */
    static int parseColor(String s) {
        if (s == null) return 0;
        String t = s.trim();
        if (!t.matches("#[0-9A-Fa-f]{6}")) return 0;
        return 0xFF000000 | Integer.parseInt(t.substring(1), 16);
    }
}
