#!/usr/bin/env bash
# Add your photos to the Family Photos screensaver:
#   export TV=<tv-ip>:5555; ./add_photos.sh photo1.jpg photo2.HEIC ...
# Each photo is turned upright, fitted to 1920x1080 (portrait photos are shown whole, never cropped),
# stripped of all metadata including GPS location, kept in my-photos/ on this computer (gitignored)
# and copied to the TV. Pick which ones play in the "Family Photos" tile on the TV.
# Needs Python 3 with Pillow:  python3 -m pip install -r tools/requirements.txt
# HEIC (iPhone) photos are converted with macOS 'sips'; on other systems convert them to JPEG first.
set -euo pipefail
source "$(dirname "$0")/tools/common.sh"
cd "$REPO"
[ $# -gt 0 ] || die "usage: ./add_photos.sh photo1.jpg [photo2.jpg ...]"
"$PYTHON" -c 'import PIL' 2>/dev/null || die "$PYTHON has no Pillow. Run: $PYTHON -m pip install -r tools/requirements.txt (or set PYTHON=/path/to/python)."
require_tv
DIR="$FILES_DIR/photos"
mkdir -p my-photos; tvsh mkdir -p "$DIR"
tmp=$(mktemp -d); n=0
for f in "$@"; do
  [ -f "$f" ] || { echo "skip $f (not a file)"; continue; }
  n=$((n+1)); name="$(date +%Y%m%d-%H%M%S)-$(printf %03d $n).jpg"; src="$f"
  case "${f##*.}" in
    heic|HEIC|heif|HEIF)
      command -v sips >/dev/null || { echo "skip $f (HEIC needs macOS sips; convert to JPEG first)"; continue; }
      sips -s format jpeg "$f" --out "$tmp/in.jpg" >/dev/null; src="$tmp/in.jpg" ;;
  esac
  "$PYTHON" -I tools/prep_photo.py "$src" "my-photos/$name"
  adb -s "$TV" push "my-photos/$name" "$DIR/$name" < /dev/null >/dev/null && echo "added $name  <- $(basename "$f")"
done
rm -rf "$tmp"
echo "TV now has $(tvsh ls "$DIR" | wc -l | tr -d ' ') photos"
