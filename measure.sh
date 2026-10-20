#!/usr/bin/env bash
# Fair speed test: free RAM, process count and cold-start time of the big apps.
# Run it ~2 minutes after a reboot, once before ./install.sh and once after.
#   export TV=<tv-ip>:5555; ./measure.sh
set -uo pipefail
source "$(dirname "$0")/tools/common.sh"
require_tv
echo "MemAvailable: $(tvsh grep MemAvailable /proc/meminfo | awk '{print int($2/1024)" MB"}')"
echo "Processes: $(tvsh ps -A | wc -l | tr -d ' ')"
echo "Home screen RAM: $(tvsh dumpsys meminfo "$(home_now | cut -d/ -f1)" | awk '/TOTAL/ {for (i = 2; i <= NF; i++) if ($i ~ /^[0-9]+$/) {print int($i/1024)" MB"; exit}}')"
for c in com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity \
         com.netflix.ninja/.MainActivity \
         in.startv.hotstar/com.hotstar.MainActivity \
         com.amazon.amazonvideo.livingroom/com.amazon.ignition.IgnitionActivity \
         com.sonyliv/.ui.splash.SplashActivity; do
  p=${c%%/*}
  tvsh pm path "$p" | grep -q package: || { echo "$p: not installed"; continue; }
  tvsh am force-stop "$p"
  echo "$p: $(tvsh am start -W -n "$c" | grep -E 'TotalTime')"
  sleep 4; tvsh input keyevent KEYCODE_HOME; sleep 3
done
