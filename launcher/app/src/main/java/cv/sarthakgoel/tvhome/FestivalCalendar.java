package cv.sarthakgoel.tvhome;

import java.time.LocalDate;

/**
 * Dated occasions for {@code "festival": "auto"}. Each entry is a run of days with its own greeting, accent,
 * festival wallpaper (theme file festivals/&lt;wallpaper&gt;.jpg) and decorations. The first entry that covers a
 * day wins, so a one-day greeting (Bhai Dooj) can sit inside a longer run. Dates are as observed in Delhi.
 * Extend the table each year; a day no entry covers is an ordinary day.
 */
final class FestivalCalendar {

    static final class Entry {
        final String id, greeting, wallpaper;
        final LocalDate start, end;
        final int accent;
        final boolean diya;
        /** The Home-press animation, one of the {@link Festival} EFFECT_* names. */
        final String effect;

        Entry(String id, String start, String end, String greeting, int accent, String wallpaper,
              boolean diya, String effect) {
            this.id = id;
            this.start = LocalDate.parse(start);
            this.end = LocalDate.parse(end);
            this.greeting = greeting;
            this.accent = accent;
            this.wallpaper = wallpaper;
            this.diya = diya;
            this.effect = effect;
        }
    }

    private static final int GOLD = 0xFFFFB23C, SAFFRON = 0xFFFF8A2B, RED = 0xFFE8433A, GREEN = 0xFF3FB27F,
            PINK = 0xFFFF4FA3, CHAMPAGNE = 0xFFF2D49B, BLUE = 0xFF4F8DFF, PLUM = 0xFFC86BFF;

    private static final String PETALS = Festival.EFFECT_PETALS, SNOW = Festival.EFFECT_SNOW,
            COLORS = Festival.EFFECT_COLORS, SPARKLES = Festival.EFFECT_SPARKLES, EMBERS = Festival.EFFECT_EMBERS,
            TRICOLOUR = Festival.EFFECT_TRICOLOUR, NONE = Festival.EFFECT_NONE;

    private static final Entry[] ENTRIES = {
            new Entry("dussehra", "2026-10-19", "2026-10-21", "Happy Dussehra", RED, "dussehra", true, PETALS),
            new Entry("karwachauth", "2026-10-29", "2026-10-29", "Happy Karwa Chauth", GOLD, "", true, NONE),
            new Entry("diwali", "2026-11-06", "2026-11-06", "Happy Dhanteras", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2026-11-07", "2026-11-07", "Happy Choti Diwali", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2026-11-08", "2026-11-09", "Happy Diwali", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2026-11-10", "2026-11-10", "Happy Govardhan Puja", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2026-11-11", "2026-11-11", "Happy Bhai Dooj", GOLD, "diwali", true, PETALS),
            new Entry("chhath", "2026-11-15", "2026-11-15", "Happy Chhath Puja", SAFFRON, "dussehra", true, NONE),
            new Entry("gurpurab", "2026-11-24", "2026-11-24", "Happy Gurpurab", SAFFRON, "diwali", true, NONE),
            new Entry("christmas", "2026-12-20", "2026-12-23", "Happy Holidays", RED, "christmas", false, SNOW),
            new Entry("christmas", "2026-12-24", "2026-12-26", "Merry Christmas", RED, "christmas", false, SNOW),
            new Entry("newyear", "2026-12-31", "2026-12-31", "Happy New Year's Eve", CHAMPAGNE, "newyear", false, SPARKLES),
            new Entry("newyear", "2027-01-01", "2027-01-02", "Happy New Year", CHAMPAGNE, "newyear", false, SPARKLES),
            new Entry("lohri", "2027-01-13", "2027-01-14", "Happy Lohri", SAFFRON, "lohri", false, EMBERS),
            new Entry("sankranti", "2027-01-15", "2027-01-15", "Happy Makar Sankranti", SAFFRON, "lohri", false, EMBERS),
            new Entry("republic", "2027-01-26", "2027-01-26", "Happy Republic Day", SAFFRON, "tricolour", false, TRICOLOUR),
            new Entry("shivratri", "2027-03-06", "2027-03-06", "Happy Maha Shivratri", BLUE, "janmashtami", true, NONE),
            new Entry("holi", "2027-03-21", "2027-03-21", "Happy Holika Dahan", SAFFRON, "lohri", false, EMBERS),
            new Entry("holi", "2027-03-22", "2027-03-23", "Happy Holi", PINK, "holi", false, COLORS),
            new Entry("baisakhi", "2027-04-14", "2027-04-14", "Happy Baisakhi", GOLD, "lohri", false, EMBERS),
            new Entry("ramnavami", "2027-04-15", "2027-04-15", "Happy Ram Navami", SAFFRON, "ganesh", true, PETALS),
            new Entry("independence", "2027-08-15", "2027-08-15", "Happy Independence Day", SAFFRON, "tricolour", false, TRICOLOUR),
            new Entry("rakhi", "2027-08-17", "2027-08-17", "Happy Raksha Bandhan", PLUM, "rakhi", false, NONE),
            new Entry("janmashtami", "2027-08-25", "2027-08-25", "Happy Janmashtami", BLUE, "janmashtami", false, NONE),
            new Entry("ganesh", "2027-09-04", "2027-09-05", "Ganpati Bappa Morya", SAFFRON, "ganesh", true, PETALS),
            new Entry("navratri", "2027-09-30", "2027-10-08", "Happy Navratri", RED, "dussehra", true, NONE),
            new Entry("dussehra", "2027-10-09", "2027-10-09", "Happy Dussehra", RED, "dussehra", true, PETALS),
            new Entry("karwachauth", "2027-10-18", "2027-10-18", "Happy Karwa Chauth", GOLD, "", true, NONE),
            new Entry("diwali", "2027-10-27", "2027-10-27", "Happy Dhanteras", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2027-10-28", "2027-10-28", "Happy Choti Diwali", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2027-10-29", "2027-10-29", "Happy Diwali", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2027-10-30", "2027-10-30", "Happy Govardhan Puja", GOLD, "diwali", true, PETALS),
            new Entry("diwali", "2027-10-31", "2027-10-31", "Happy Bhai Dooj", GOLD, "diwali", true, PETALS),
            new Entry("chhath", "2027-11-04", "2027-11-04", "Happy Chhath Puja", SAFFRON, "dussehra", true, NONE),
            new Entry("gurpurab", "2027-11-14", "2027-11-14", "Happy Gurpurab", SAFFRON, "diwali", true, NONE),
            new Entry("christmas", "2027-12-20", "2027-12-23", "Happy Holidays", RED, "christmas", false, SNOW),
            new Entry("christmas", "2027-12-24", "2027-12-26", "Merry Christmas", RED, "christmas", false, SNOW),
            new Entry("newyear", "2027-12-31", "2027-12-31", "Happy New Year's Eve", CHAMPAGNE, "newyear", false, SPARKLES),
            new Entry("newyear", "2028-01-01", "2028-01-02", "Happy New Year", CHAMPAGNE, "newyear", false, SPARKLES)
    };

    private FestivalCalendar() {}

    static Entry on(LocalDate day) {
        for (Entry e : ENTRIES) {
            if (!day.isBefore(e.start) && !day.isAfter(e.end)) return e;
        }
        return null;
    }
}
