# Usage: python3 tools/prep_photo.py in.jpg out.jpg   (add_photos.sh calls this for you)
# Upright, metadata (incl. GPS) stripped, JPEG q88, exactly 1920x1080.
# Photos narrower than 16:9 (portrait, 4:3 prints) are shown whole over a soft blurred copy of themselves,
# so the TV's full-screen crop never cuts off a face.
import sys
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
src, dst = sys.argv[1], sys.argv[2]
W, H = 1920, 1080
im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
if im.width / im.height >= 1.7:
    out = ImageOps.fit(im, (W, H), Image.LANCZOS)
else:
    bg = ImageOps.fit(im, (W // 4, H // 4), Image.LANCZOS).filter(ImageFilter.GaussianBlur(12)).resize((W, H), Image.LANCZOS)
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    fg = im.copy(); fg.thumbnail((int(W * 0.92), int(H * 0.92)), Image.LANCZOS)
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    out = bg
out.save(dst, "JPEG", quality=88, optimize=True)
