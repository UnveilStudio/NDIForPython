"""
Generate the README banner.

Run:
    python assets/build_banner.py

Outputs assets/banner.png (1280x320 PNG) used as the README hero.
"""
from __future__ import annotations
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "assets" / "unveil_logo.png"
OUT  = ROOT / "assets" / "banner.png"

W, H = 1280, 320

TITLE   = "NDIForPython"
TAGLINE = "Real-time NDI® video for Python  ·  Windows x64"
FOOTER  = "Unveil Studio  ·  MIT License  ·  NDI® is a trademark of Vizrt"

# NDI banner accent: cyan-teal — distinguishes it visually from spout2-python.
ACCENT = (90, 200, 230)
GLOW   = (15, 60, 95)


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = {
        "bold":    ["seguivb.ttf", "segoeuib.ttf", "arialbd.ttf"],
        "regular": ["seguivar.ttf", "segoeui.ttf", "arial.ttf"],
        "light":   ["seguivar.ttf", "segoeuil.ttf", "arial.ttf"],
    }[weight]
    for name in candidates:
        path = os.path.join(r"C:\Windows\Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), (5, 8, 10))
    glow = Image.new("RGB", (W, H), (5, 8, 10))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-200, -100, 600, H + 100), fill=GLOW)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=120))
    img = Image.blend(img, glow, alpha=0.55)

    draw = ImageDraw.Draw(img)

    logo_target = 220
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((logo_target, logo_target), Image.LANCZOS)
    pad_left = 64
    img.paste(logo, (pad_left, (H - logo.height) // 2), logo)

    text_x = pad_left + logo_target + 56
    title_font   = _font("bold", 78)
    tagline_font = _font("regular", 28)
    footer_font  = _font("regular", 18)

    bbox = draw.textbbox((0, 0), TITLE, font=title_font)
    title_h = bbox[3] - bbox[1]
    title_y = (H - title_h) // 2 - 24
    draw.text((text_x, title_y), TITLE, font=title_font, fill=(245, 248, 250))

    draw.rectangle(
        (text_x, title_y + title_h + 14, text_x + 110, title_y + title_h + 18),
        fill=ACCENT,
    )

    draw.text(
        (text_x, title_y + title_h + 32),
        TAGLINE,
        font=tagline_font,
        fill=(190, 200, 210),
    )

    fb = draw.textbbox((0, 0), FOOTER, font=footer_font)
    draw.text(
        (W - (fb[2] - fb[0]) - 40, H - (fb[3] - fb[1]) - 28),
        FOOTER,
        font=footer_font,
        fill=(110, 120, 130),
    )

    img.save(OUT, optimize=True)
    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT}  ({W}x{H}, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
