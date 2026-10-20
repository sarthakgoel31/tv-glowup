#!/usr/bin/env bash
# Snapshot the TV: every package and whether it is enabled, all settings, and copies of the apps you
# installed yourself. Read-only: nothing on the TV changes.
#   export TV=<tv-ip>:5555; ./backup.sh            -> backups/<timestamp>/ (and backups/latest)
# The first backup ever taken is also kept as backups/original; ./restore.sh goes back to it.
set -euo pipefail
source "$(dirname "$0")/tools/common.sh"
cd "$REPO"
require_tv
ts=$(date +%Y%m%d-%H%M%S); d="backups/$ts"; mkdir -p "$d/apks"
tvsh getprop > "$d/getprop.txt"
tvsh pm list packages -f -u > "$d/all_packages.txt"
tvsh pm list packages -e | sed 's/package://' | sort > "$d/enabled.txt"
tvsh pm list packages -d | sed 's/package://' | sort > "$d/disabled.txt"
tvsh pm list packages -s | sed 's/package://' | sort > "$d/system.txt"
tvsh pm list packages -3 | sed 's/package://' | sort > "$d/user_installed.txt"
for ns in global secure system; do tvsh settings list $ns > "$d/settings_$ns.txt"; done
tvsh device_config get activity_manager max_cached_processes > "$d/max_cached_processes.txt" || echo null > "$d/max_cached_processes.txt"
home_now > "$d/home.txt" || true
# Copy user-installed APKs so they can be reinstalled even if something removes them later.
while read -r p; do
  [ -n "$p" ] || continue
  for path in $(tvsh pm path "$p" | sed 's/package://'); do
    adb -s "$TV" pull "$path" "$d/apks/${p}__$(basename "$path")" < /dev/null >/dev/null 2>&1 || echo "skip $p"
  done
done < "$d/user_installed.txt"
ln -sfn "$ts" backups/latest
[ -e backups/original ] || ln -sfn "$ts" backups/original
echo "Backup in $d: $(wc -l < "$d/enabled.txt" | tr -d ' ') enabled, $(wc -l < "$d/disabled.txt" | tr -d ' ') disabled, $(ls "$d/apks" | wc -l | tr -d ' ') apks"
