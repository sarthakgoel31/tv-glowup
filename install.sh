#!/usr/bin/env bash
# TV Glowup: make a slow Android TV fast and good-looking, over Wi-Fi.
#   export TV=<tv-ip>:5555
#   ./install.sh
# What it does, in order (every step is undone by ./restore.sh):
#   1. backup     snapshot of every package + setting (backups/, never uploaded anywhere)
#   2. debloat    pm disable-user on the list in devices/<device>/disable.txt (nothing is uninstalled)
#   3. launcher   builds the TV Glowup Home app, installs it, starts it and checks it really came up
#   4. theme      pushes themes/india (festival calendar, wallpapers, weather/time-of-day backgrounds)
#   5. Home       makes it the Home screen; the stock launcher is disabled only if it was the Home,
#                 and only after ours started. If Home doesn't end up ours, everything is rolled back.
#   6. extras     remote-key accessibility service, Family Photos screensaver, background-app limit
# Options (environment variables):
#   DEVICE=oneplus-y-series-android11   which debloat list to use (folder in devices/); DEVICE=none skips it
#   THEME=india                         which theme folder in themes/ to push
#   APK=path/to/app.apk                 skip the build and install this APK instead
#   SHOW_WIFI_NAME=1                    let the Wi-Fi pill show your network name (grants location permission)
set -euo pipefail
source "$(dirname "$0")/tools/common.sh"
cd "$REPO"
require_tv
DEVICE="${DEVICE:-oneplus-y-series-android11}"
THEME="${THEME:-india}"
STOCK=com.google.android.tvlauncher
step() { printf '\n== %s\n' "$*"; }

echo "TV: $TV  ($(tvsh getprop ro.product.manufacturer) $(tvsh getprop ro.product.model), Android $(tvsh getprop ro.build.version.release))"

step "1/6 Backup"
./backup.sh

step "2/6 Debloat ($DEVICE)"
if [ "$DEVICE" = none ]; then echo "skipped"
else
  LIST="devices/$DEVICE/disable.txt"
  [ -f "$LIST" ] || die "no debloat list at $LIST (see devices/, or DEVICE=none to skip)"
  n=0
  while read -r line; do
    p=$(printf '%s' "${line%%#*}" | tr -d '[:space:]')
    [ -n "$p" ] || continue
    if tvsh pm path "$p" | grep -q package:; then
      tvsh pm disable-user --user 0 "$p" | grep -q 'new state' && { echo "disabled $p"; n=$((n+1)); } || echo "could not disable $p"
    fi
  done < "$LIST"
  echo "$n apps disabled (undo: ./restore.sh, or adb shell pm enable <package>)"
fi

step "3/6 Launcher"
if [ -z "${APK:-}" ]; then
  # macOS Homebrew defaults; set JAVA_HOME / ANDROID_HOME yourself on other systems.
  [ -n "${JAVA_HOME:-}" ] || { [ -d /opt/homebrew/opt/openjdk@17 ] && export JAVA_HOME=/opt/homebrew/opt/openjdk@17; } || true
  [ -n "${ANDROID_HOME:-}" ] || for sdk in ~/Library/Android/sdk ~/Android/Sdk /opt/homebrew/share/android-commandlinetools; do
    [ -d "$sdk" ] && export ANDROID_HOME="$sdk" && break
  done
  [ -n "${JAVA_HOME:-}" ] || die "set JAVA_HOME to a JDK 17 (macOS: brew install openjdk@17), or pass APK=<prebuilt apk>"
  [ -n "${ANDROID_HOME:-}" ] || die "set ANDROID_HOME to your Android SDK (macOS: brew install --cask android-commandlinetools), or pass APK=<prebuilt apk>"
  export PATH="$JAVA_HOME/bin:$PATH"
  (cd launcher && { [ -f local.properties ] || echo "sdk.dir=$ANDROID_HOME" > local.properties; } && ./gradlew assembleRelease -q --console=plain)
  APK=launcher/app/build/outputs/apk/release/app-release.apk
fi
[ -f "$APK" ] || die "APK not found: $APK"
out=$(adb -s "$TV" install -r "$APK" < /dev/null 2>&1 || true); echo "$out"
case "$out" in *Success*) ;; *) die "install failed; Home was not touched. ./restore.sh undoes the debloat." ;; esac
tvsh cmd package compile -m speed -f "$PKG" >/dev/null 2>&1 || true
if [ "${SHOW_WIFI_NAME:-0}" = 1 ]; then tvsh pm grant "$PKG" android.permission.ACCESS_FINE_LOCATION || true; fi

step "4/6 Theme ($THEME)"
T="themes/$THEME"
[ -f "$T/config.json" ] || die "no theme at $T"
tvsh mkdir -p "$FILES_DIR/festivals" "$FILES_DIR/ambient"
adb -s "$TV" push "$T/config.json" "$FILES_DIR/config.json" < /dev/null >/dev/null
[ -f "$T/wallpaper.jpg" ] && adb -s "$TV" push "$T/wallpaper.jpg" "$FILES_DIR/wallpaper.jpg" < /dev/null >/dev/null
if [ -d "$T/festivals" ]; then
  for f in "$T"/festivals/*.jpg; do adb -s "$TV" push "$f" "$FILES_DIR/festivals/" < /dev/null >/dev/null; done
fi
if [ -d "$T/ambient" ]; then
  for f in "$T"/ambient/*.jpg; do adb -s "$TV" push "$f" "$FILES_DIR/ambient/" < /dev/null >/dev/null; done
fi
# A fresh marker makes the launcher drop old on-TV layout choices and re-read the theme.
tvsh "printf '%s' '$(date +%s)$$' > $FILES_DIR/theme_revision"
echo "theme pushed"

step "5/6 Home screen"
tvsh am force-stop "$PKG" || true
start=$(tvsh am start -W -n "$PKG/.MainActivity" 2>&1 || true); echo "$start"
if ! printf '%s' "$start" | grep -qF 'Status: ok' || printf '%s' "$start" | grep -qi '^Error'; then
  die "TV Glowup Home did not start; the stock launcher was not touched."
fi
before=$(home_now); echo "Home was: $before"
disabled_stock=0
case "$before" in
  "$PKG"/*) echo "already ours" ;;
  "$STOCK"/*) tvsh pm disable-user --user 0 "$STOCK" >/dev/null && disabled_stock=1 && echo "disabled $STOCK" ;;
  *) echo "Home is not $STOCK, so no launcher is disabled (you may get a 'choose Home app' prompt: pick TV Glowup Home)." ;;
esac
tvsh cmd package set-home-activity --user 0 "$PKG/.MainActivity" >/dev/null 2>&1 || true
after=$(home_now); echo "Home now: $after"
case "$after" in
  "$PKG"/*) ;;
  *)
    echo "Home did not switch to TV Glowup Home. Rolling back." >&2
    if [ "$disabled_stock" = 1 ]; then
      tvsh pm enable "$STOCK" >/dev/null
      tvsh cmd package set-home-activity --user 0 "$(tvsh cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME "$STOCK" | tail -n 1)" >/dev/null 2>&1 || true
    fi
    die "Home is back to: $(home_now). Run ./restore.sh to undo the rest."
    ;;
esac

step "6/6 Extras"
# Remote keys (Input/TV button opens the input switcher from any app): an accessibility service.
# Android sometimes accepts the setting without binding the service, so check and retry.
for i in 1 2 3; do adb -s $TV shell settings put secure enabled_accessibility_services cv.sarthakgoel.tvhome/.InputKeyService; adb -s $TV shell settings put secure accessibility_enabled 1; sleep 3; adb -s $TV shell dumpsys accessibility | grep -m1 'Bound services' | grep -q 'label=' && break; adb -s $TV shell settings put secure enabled_accessibility_services '""'; sleep 1; done
if tvsh dumpsys accessibility | grep -m1 'Bound services' | grep -q 'label='; then echo "remote-key service on"
else echo "remote-key service did not bind (Home still works; re-run ./install.sh later to retry)"; fi
# Family Photos screensaver.
tvsh settings put secure screensaver_components "$PKG/.PhotoDream"
tvsh settings put secure screensaver_enabled 1
echo "screensaver: Family Photos (add photos with ./add_photos.sh)"
# Keep at most 4 apps cached in the background: a 1 GB TV stops thrashing.
tvsh device_config put activity_manager max_cached_processes 4
echo "background-app limit: 4"

printf '\nDone. Press Home on the remote. Undo everything: ./restore.sh\n'
