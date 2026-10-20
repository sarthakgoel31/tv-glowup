# TV Glowup

**Make a slow, cheap Android TV fast and beautiful in 10 minutes, over Wi-Fi. No root, nothing uninstalled, one command to undo.**

⭐ **Star this repo if it made your TV faster.** It helps other people with the same TV find it.

![Home screen during Dussehra](docs/screenshots/home-dussehra.png)

## Before / after

Measured with `./measure.sh` on a **OnePlus Y Series, 1 GB RAM, Android 11**, ~2 minutes after boot.

![Before/after chart: apps open about twice as fast, free RAM up from 162 MB to 265 MB](docs/speed.png)

| | Before | After |
|---|---|---|
| Free RAM | 162 MB | **~265 MB** |
| Home screen RAM | 132 MB | **69 MB** |
| YouTube opens in | 2.9 s | **~1.5 s** |
| Netflix | 2.8 s | **~1.0 s** |
| JioHotstar | 5.5 s | **~2.3 s** |
| SonyLIV | 6.2 s | **~3.5 s** |
| Prime Video | no gain | no gain |

## What you get

- **Debloat with full restore.** Disables (never uninstalls) the preinstalled apps and Google extras that eat RAM. A full backup is taken first; `./restore.sh` puts everything back.
- **Apple-TV-style Home.** Big 4x2 grid of your apps, clock and date, nothing else. Light enough for 1 GB RAM.
- **Festival calendar, automatic.** Greetings, festival backgrounds and a Home-press animation (petals, fireworks...) for Diwali, Dussehra, Holi, Rakhi, Ganesh Chaturthi, Janmashtami, Lohri, Independence/Republic Day, Christmas and New Year, with a diya by the greeting. Dates through Jan 2028, from Drik Panchang. See all backgrounds: [docs/festivals.jpg](docs/festivals.jpg).
- **Live weather and time of day.** The background follows the sky outside: dawn, day, dusk, night, plus cloudy, rain, storm, fog, hot and cold. Pressing Home plays a matching effect (rain, a storm flash, drifting fog...). Free, no account. See [below](#live-weather--time-of-day).
- **Family photo screensaver.** Your photos when the TV is idle, plus a **Family Photos** tile to pick which ones play.
- **Boots straight to Home**, even on MediaTek TVs that force Live TV at power-on.
- **HDMI / Wi-Fi / Settings pills** at the top: one click to switch input or open settings.
- **App library** to add or remove apps from Home.

| Home-press animation | All apps + App library | Family Photos picker |
|---|---|---|
| ![](docs/screenshots/petals.png) | ![](docs/screenshots/library.png) | ![](docs/screenshots/photos-picker.png) |

## Gallery

**Festival backgrounds.** Every one is drawn by code (`tools/wallgen/make_walls.py`), no stock art. Shown with a mock of the Home layout on top:

![All festival backgrounds under a mock Home screen](docs/festivals-mock.jpg)

**Diwali Home**, with the 4x2 app grid:

![Home screen during Diwali](docs/screenshots/home-diwali.png)

**Home-button animations**, real screenshots from the TV. Weather ones play on ordinary days, festival ones on their dates. Each is a 2-3 s Canvas effect with under 1% janky frames on a 1 GB TV:

![Rain, storm, fog, hot, cold, cloudy, Christmas snow, Holi colours, New Year fireworks, Lohri embers, tricolour confetti and Diwali petals](docs/effects.jpg)

## Quick start

You need a laptop on the same Wi-Fi as the TV, with `adb` (macOS: `brew install android-platform-tools`), Java 17 and the Android SDK to build the launcher (macOS: `brew install openjdk@17` and `brew install --cask android-commandlinetools`).

1. **On the TV:** Settings > Device Preferences > About > press OK on **Build** 7 times. Then Developer options > turn on **USB debugging** / **Network debugging**.
2. Note the TV's IP: Settings > Network & Internet > your Wi-Fi.
3. **On the laptop:**
   ```bash
   git clone https://github.com/sarthakgoel31/tv-glowup && cd tv-glowup
   export TV=192.168.x.x:5555     # your TV's IP
   ./install.sh
   ```
4. The TV asks **Allow USB debugging?** the first time: tick *Always allow*, press OK.

Press Home on the remote. Done.

Options: `DEVICE=none ./install.sh` skips the debloat (launcher only). `SHOW_WIFI_NAME=1` lets the Wi-Fi pill show your network name (it needs the location permission for that). `APK=app.apk` installs a prebuilt APK instead of building.

## Add your photos

```bash
pip3 install -r tools/requirements.txt
./add_photos.sh ~/Pictures/diwali-2026/*.jpg
```

Photos are turned upright, fitted to the screen (portrait photos are shown whole, never cropped) and **stripped of GPS location and all metadata** before they leave your laptop. Then open the **Family Photos** tile on the TV to choose which ones play.

<img src="launcher/app/src/main/res/drawable-nodpi/banner_photos.png" alt="Family Photos tile" width="320">

## Live weather & time of day

On ordinary days the Home background changes with the time and the weather outside:

- **Time of day**: dawn, day, dusk and night, timed from your sunrise and sunset. This works with no setup at all.
- **Weather**: cloudy, rain, storm, fog (smog counts), hot and cold versions, from [Open-Meteo](https://open-meteo.com) (free, no API key, no account). The TV checks at most every 30 minutes; offline, it keeps the last reading for 3 hours, then falls back to time of day only.
- **Home-press weather effects**: rain streaks, a storm with a soft flash, drifting fog, heat shimmer, frost glints or passing clouds. Turn them off with `"weather_effects": false`.
- **The temperature** appears after the date.
- **Festivals take priority**: on Diwali, Holi and the rest, the festival background and animation win over the weather.

![The 12 weather and time-of-day backgrounds under a mock Home screen](docs/ambient-mock.jpg)

**Turn on weather** by setting your location in `themes/india/config.json`, then run `./install.sh` again:

```json
"weather_lat": "19.08",
"weather_lon": "72.88"
```

To find your numbers: open [Google Maps](https://maps.google.com), right-click your area and click the first line of the menu (two numbers like `19.0760, 72.8777`). The first is `weather_lat`, the second `weather_lon`. Two decimals (about 1 km) are plenty; use your city or neighbourhood, not your exact house. Leave both empty (`""`, the default) to keep weather off: no request is ever made then.

The backgrounds are drawn by code too: `tools/wallgen/make_ambient.py` (all 12 without the mock: [docs/ambient.jpg](docs/ambient.jpg)). Replace any of them with your own `themes/india/ambient/<name>.jpg`, 1920x1080.

## Make it yours

Edit `themes/india/config.json` and run `./install.sh` again:

| Key | What it does |
|---|---|
| `greeting_name` | Name after the greeting, e.g. `"Sharma Family"` shows *HAPPY DIWALI, SHARMA FAMILY*. Empty by default. |
| `dock_apps` | Apps in the top row, in order (package names). |
| `hidden_apps` | Apps never shown on Home. |
| `festival` | `"auto"` follows the calendar. |
| `reduced_motion` | `true` keeps animations light for slow TVs. |
| `weather_lat`, `weather_lon` | Your area for live weather, e.g. `"19.08"` and `"72.88"`. Empty turns weather off. |
| `weather_effects` | `false` stops the Home-press weather animations. |

Festival backgrounds are generated by `tools/wallgen/make_walls.py`; add your own as `themes/india/festivals/<id>.jpg`.

## Undo everything

```bash
./restore.sh
```

Re-enables every app, removes TV Glowup Home, and puts accessibility, screensaver and background-app settings back exactly as the first backup found them. Reboot the TV once after.

## Works on

| TV | Android | Status |
|---|---|---|
| OnePlus Y Series (1 GB RAM) | 11 | ✅ Tested |
| Other Android TV / Google TV | 9+ | Likely works. Use `DEVICE=none` or write your own list in `devices/`. At your own risk. |

Installed it on another TV? [Tell us here](../../issues/new?template=installed.yml) so it goes on this list.

## Safety

- **Nothing is uninstalled.** The debloat uses `pm disable-user`; every app can be turned back on with `pm enable` or `./restore.sh`. The full list, with what each app is, is in [devices/oneplus-y-series-android11/disable.txt](devices/oneplus-y-series-android11/disable.txt).
- **Backup first, always.** `install.sh` runs `backup.sh` before touching anything. Backups stay in `backups/` on your laptop.
- **Home is switched safely.** The new Home is installed and started first. The stock launcher is disabled only if it was the Home, and if Home doesn't end up on TV Glowup the stock launcher is put back.
- Nothing is sent anywhere. No accounts, no analytics. The only network request the launcher makes is the optional weather lookup to Open-Meteo, and only after you set `weather_lat`/`weather_lon`; it sends those two numbers and nothing else.

## FAQ

**Why not root?** Rooting a TV voids the warranty, can brick it and blocks OTA updates. Everything here uses normal developer-mode `adb`, which Android allows on every TV.

**Will Netflix / Hotstar / YouTube still work?** Yes. Only apps in the debloat list are disabled; streaming apps you use are untouched.

**Did Prime Video get faster?** No. It's the one app that didn't improve in testing.

**A system update re-enabled some apps.** Run `./install.sh` again.

**The TV shows "Choose a Home app".** Pick TV Glowup Home and choose *Always*.

**How do I go back to the old home screen?** `./restore.sh`.

**Can I use it on Windows?** Run the scripts in Git Bash or WSL with `adb` on the PATH.

---

Made by Sarthak Goel to speed up his own OnePlus TV. MIT licensed, see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
