package cv.sarthakgoel.tvhome;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class WeatherTest {
    @Test
    public void conditions() {
        assertEquals("storm", Weather.condition(95, 30, true, 100, -1));
        assertEquals("rain", Weather.condition(61, 30, true, 100, -1));
        assertEquals("rain", Weather.condition(81, 30, false, 100, -1));
        assertEquals("fog", Weather.condition(45, 20, true, 0, -1));
        assertEquals("fog", Weather.condition(0, 20, true, 0, 180));
        assertEquals("cold", Weather.condition(73, 2, true, 100, -1));
        assertEquals("hot", Weather.condition(1, 39, true, 0, 40));
        assertEquals("clear", Weather.condition(1, 39, false, 0, 40));
        assertEquals("cold", Weather.condition(0, 7, true, 0, -1));
        assertEquals("cloudy", Weather.condition(3, 25, true, 40, -1));
        assertEquals("cloudy", Weather.condition(2, 25, true, 80, -1));
        assertEquals("clear", Weather.condition(1, 25, true, 20, 90));
    }

    @Test
    public void slots() {
        int sr = 6 * 60 + 30, ss = 17 * 60 + 45;
        assertEquals("night", Weather.slot(5 * 60 + 44, sr, ss));
        assertEquals("dawn", Weather.slot(5 * 60 + 45, sr, ss));
        assertEquals("dawn", Weather.slot(7 * 60 + 44, sr, ss));
        assertEquals("day", Weather.slot(7 * 60 + 45, sr, ss));
        assertEquals("dusk", Weather.slot(16 * 60 + 45, sr, ss));
        assertEquals("dusk", Weather.slot(18 * 60 + 24, sr, ss));
        assertEquals("night", Weather.slot(18 * 60 + 25, sr, ss));
        assertEquals("night", Weather.slot(0, sr, ss));
    }

    @Test
    public void ambientPicks() {
        assertEquals("storm", Weather.ambient("storm", "night"));
        assertEquals("rain-night", Weather.ambient("rain", "night"));
        assertEquals("rain-day", Weather.ambient("rain", "dusk"));
        assertEquals("hot", Weather.ambient("hot", "day"));
        assertEquals("cold", Weather.ambient("cold", "day"));
        assertEquals("night", Weather.ambient("cold", "night"));
        assertEquals("cloudy-night", Weather.ambient("cloudy", "night"));
        assertEquals("dusk", Weather.ambient("clear", "dusk"));
        assertEquals("dawn", Weather.ambient(null, "dawn"));
        assertEquals(390, Weather.minuteOf("2026-10-21T06:30", 0));
        assertEquals(7, Weather.minuteOf("bad", 7));
    }
}
