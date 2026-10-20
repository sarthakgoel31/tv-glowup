#!/usr/bin/env bash
# Put the TV back exactly as a backup found it:
#   - re-enable every package that was enabled (and reinstall any that went missing)
#   - remove apps added after the backup (this removes the TV Glowup launcher)
#   - put back accessibility, screensaver and the background-app limit as they were
#   export TV=<tv-ip>:5555; ./restore.sh                     # back to backups/original
#   ./restore.sh backups/20260101-120000                      # or any other backup
set -uo pipefail
source "$(dirname "$0")/tools/common.sh"
cd "$REPO"
require_tv
d="${1:-backups/original}"
[ -f "$d/enabled.txt" ] || die "no backup at $d (run ./backup.sh first, or pass a backup folder)."
echo "Restoring from $d"

# 1. Everything that was enabled comes back.
while read -r p; do
  [ -n "$p" ] || continue
  tvsh cmd package install-existing "$p" >/dev/null 2>&1
  tvsh pm enable "$p" >/dev/null 2>&1
done < "$d/enabled.txt"
if [ -d "$d/apks" ]; then
  for p in $(ls "$d"/apks 2>/dev/null | sed 's/__.*//' | sort -u); do
    tvsh pm path "$p" | grep -q package: || adb -s "$TV" install-multiple -r "$d"/apks/"$p"__*.apk
  done
fi

# 2. Settings as they were in the backup ("null" = was never set, so delete it).
orig() { grep -m1 "^$1=" "$d/settings_secure.txt" 2>/dev/null | cut -d= -f2-; }
put_back() {
  local key=$1 val
  val=$(orig "$key")
  if [ -z "$val" ] || [ "$val" = null ]; then tvsh settings delete secure "$key" >/dev/null 2>&1
  else tvsh settings put secure "$key" "$val" >/dev/null 2>&1; fi
}
put_back enabled_accessibility_services
v=$(orig accessibility_enabled); tvsh settings put secure accessibility_enabled "${v:-0}" >/dev/null 2>&1
put_back screensaver_components
put_back screensaver_enabled
mc=$(cat "$d/max_cached_processes.txt" 2>/dev/null || echo null)
if [ -z "$mc" ] || [ "$mc" = null ]; then tvsh device_config delete activity_manager max_cached_processes >/dev/null 2>&1
else tvsh device_config put activity_manager max_cached_processes "$mc" >/dev/null 2>&1; fi

# 3. Apps added after the backup go (the TV Glowup launcher included), so the stock Home is back.
for p in $(tvsh pm list packages -3 | sed 's/package://'); do
  grep -qx "$p" "$d/user_installed.txt" || { echo "removing $p"; adb -s "$TV" uninstall "$p" < /dev/null; }
done
stock=$(cut -d/ -f1 "$d/home.txt" 2>/dev/null || true)
if [ -n "$stock" ] && [ "$stock" != android ] && [ "$stock" != "$PKG" ]; then
  tvsh cmd package set-home-activity --user 0 "$(tvsh cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME "$stock" | tail -n 1)" >/dev/null 2>&1
fi
echo "Home now: $(home_now)"

# 4. Check.
now=$(mktemp)
tvsh pm list packages -e | sed 's/package://' | sort > "$now"
missing=$(comm -23 "$d/enabled.txt" "$now"); rm -f "$now"
if [ -z "$missing" ]; then echo "Restore OK: every package from $d is enabled again. Reboot the TV once."
else echo "Still missing:"; echo "$missing"; exit 1; fi
