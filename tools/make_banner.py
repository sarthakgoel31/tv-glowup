# Family Photos tile banner, 640x360 (shown at 320x180dp-ish on the TV).
# Usage: python3 tools/make_banner.py launcher/app/src/main/res/font/outfit.ttf banner_photos.png
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont
W, H = 640, 360
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
for y in range(H):  # warm plum-to-amber gradient
    t = y / H
    d.line([(0, y), (W, y)], fill=(int(60 + 140 * t), int(24 + 70 * t), int(70 - 30 * t)))
glow = Image.new("L", (W, H), 0)
ImageDraw.Draw(glow).ellipse([W * 0.45, -H * 0.4, W * 1.3, H * 0.9], fill=150)
img = Image.composite(Image.new("RGB", (W, H), (255, 190, 110)), img, glow.filter(ImageFilter.GaussianBlur(70)))
d = ImageDraw.Draw(img)
# three overlapping "photos"
for i, (x, y, a) in enumerate([(70, 70, -10), (120, 60, 4), (170, 78, 14)]):
    card = Image.new("RGBA", (190, 150), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, 189, 149], 14, fill=(250, 246, 238, 255))
    cd.rounded_rectangle([10, 10, 179, 112], 8, fill=[(250, 160, 80), (120, 170, 230), (240, 120, 150)][i])
    cd.ellipse([120, 22, 150, 52], fill=(255, 240, 200))
    cd.polygon([(10, 112), (70, 55), (120, 112)], fill=(60, 90, 70))
    card = card.rotate(a, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", card.size, (0, 0, 0, 0)); sh.putalpha(card.split()[3].point(lambda v: v * 0.45))
    img.paste((0, 0, 0), (x + 6, y + 10), sh.split()[3].filter(ImageFilter.GaussianBlur(8)))
    img.paste(card, (x, y), card)
font = ImageFont.truetype(sys.argv[1], 46)
d.text((392, 140), "Family", font=font, fill=(255, 255, 255))
d.text((392, 192), "Photos", font=font, fill=(255, 236, 200))
img.save(sys.argv[2])
