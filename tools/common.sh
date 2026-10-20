# Shared by every script in this repo. Source it, don't run it.
# shellcheck shell=bash
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG=cv.sarthakgoel.tvhome
PYTHON="${PYTHON:-python3}"
FILES_DIR="/sdcard/Android/data/$PKG/files"

die() { echo "ERROR: $*" >&2; exit 1; }

# TV=<ip>:5555 must be set. Port 5555 is added if you leave it out.
require_tv() {
  command -v adb >/dev/null 2>&1 || die "adb not found. Install it: macOS 'brew install android-platform-tools', Ubuntu 'sudo apt install adb', Windows: Google 'SDK Platform Tools'."
  if [ -z "${TV:-}" ]; then
    echo "ERROR: TV is not set." >&2
    echo "  1. On the TV: Settings > Device Preferences > About > press OK on 'Build' 7 times (developer mode)." >&2
    echo "  2. Settings > Device Preferences > Developer options > turn on 'Network debugging' / 'USB debugging'." >&2
    echo "  3. Find the TV's IP in Settings > Network & Internet > your Wi-Fi." >&2
    echo "  4. export TV=<that-ip>:5555   then run this script again." >&2
    exit 1
  fi
  case "$TV" in *:*) ;; *) TV="$TV:5555" ;; esac
  export TV
  adb connect "$TV" >/dev/null 2>&1 || true
  local state
  state=$(adb -s "$TV" get-state 2>&1 | tr -d '\r') || true
  [ "$state" = device ] || die "cannot reach $TV over adb ($state). Is the TV on and on the same Wi-Fi? If the TV shows an 'Allow debugging?' prompt, tick 'Always allow' and press OK, then run again."
}

# Run a shell command on the TV (stdin closed so it never eats a loop's input).
tvsh() { adb -s "$TV" shell "$@" < /dev/null | tr -d '\r'; }

# Which activity answers the Home button right now, e.g. com.google.android.tvlauncher/.MainActivity
home_now() {
  tvsh cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -n 1
}
