#!/usr/bin/env python3
"""Draw the installer's branded artwork (launch plan 5.2; Mihai, 2026-09-25: "can the installer
itself be customized more to show the Armada branding?").

    python tools/build_installer_art.py        # needs Pillow + cairosvg; writes installer/art/*.png

Inno Setup 7 shows two images (https://jrsoftware.org/ishelp/topic_setup_wizardimagefile.htm):

- the **panel** on the left of the Welcome and Finished pages, 164:314, at 202x386 / 269x515 /
  336x643 / 430x824 for 100–200% display scaling; and
- the **mark** at the top right of every other page, square, 58 / 77 / 97 / 124 px.

The panel is ARMADA's navy (the dark end of the accent scale) with the white lockup and tagline,
so it reads the same whether Windows is in light or dark mode. The mark is the colour symbol for
light mode and the white one for dark (`WizardStyle=modern dynamic` follows Windows).

Sources live beside the output in installer/art/src: Mihai's logo SVGs and Barlow Condensed (OFL,
licence beside it). The PNGs are committed, so building the installer doesn't need this script.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ART = Path(__file__).resolve().parents[1] / "installer" / "art"
SRC = ART / "src"
PANEL_SIZES = [(202, 386), (269, 515), (336, 643), (430, 824)]
MARK_SIZES = [58, 77, 97, 124]
NAVY_TOP, NAVY_BOTTOM = (4, 23, 51), (8, 48, 106)          # --color-accent-900 → -700
TEAL = (18, 163, 184)                                      # --color-accent-2
TAGLINE = "Your standing team of minds"


def _svg(name: str, width: int) -> Image.Image:
    im = Image.open(io.BytesIO(cairosvg.svg2png(url=str(SRC / name), output_width=width))).convert("RGBA")
    return im.crop(im.getbbox())


def panel(w: int, h: int) -> Image.Image:
    S = 3                                                  # draw big, shrink once: crisp edges
    W, H = w * S, h * S
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):                                     # the navy gradient, top to bottom
        t = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOTTOM)))
    glow = Image.new("L", (W, H), 0)                       # a low teal glow rising from the bottom
    ImageDraw.Draw(glow).ellipse([-W * 0.4, H * 0.72, W * 1.4, H * 1.45], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(W * 0.18))
    img = Image.composite(Image.new("RGB", (W, H), TEAL), img, glow.point(lambda v: v * 0.55))
    # the symbol's slant, as faint strokes across the panel
    lines = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(lines)
    step = W * 0.22
    for i in range(-6, 12):
        x0 = i * step
        d.line([(x0, H), (x0 + H * math.tan(math.radians(28)), 0)], fill=10, width=max(2, W // 110))
    img = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, lines)
    img = img.convert("RGBA")
    lock = _svg("lockup-white.svg", 3000)
    lw = int(W * 0.72)
    lock = lock.resize((lw, round(lock.height * lw / lock.width)), Image.LANCZOS)
    top = int(H * 0.30)
    img.alpha_composite(lock, ((W - lw) // 2, top))
    font = ImageFont.truetype(str(SRC / "BarlowCondensed-Medium.ttf"), size=int(W * 0.078))
    dd = ImageDraw.Draw(img)
    tw = dd.textlength(TAGLINE.upper(), font=font)
    dd.text(((W - tw) / 2, top + lock.height + H * 0.035), TAGLINE.upper(), font=font,
            fill=(141, 216, 226))                          # --color-accent-2-300
    pill_font = ImageFont.truetype(str(SRC / "BarlowCondensed-SemiBold.ttf"), size=int(W * 0.06))
    label = "BETA"
    bw = dd.textlength(label, font=pill_font) + W * 0.07
    bh = W * 0.1
    bx, by = (W - bw) / 2, H * 0.88
    dd.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2, outline=(141, 216, 226),
                         width=max(2, W // 160))
    dd.text((bx + (bw - dd.textlength(label, font=pill_font)) / 2, by + bh * 0.12), label,
            font=pill_font, fill=(141, 216, 226))
    return img.convert("RGB").resize((w, h), Image.LANCZOS)


def mark(size: int, white: bool) -> Image.Image:
    sym = _svg("symbol-white.svg" if white else "symbol.svg", 2000)
    pad = round(size * 0.08)
    box = size - 2 * pad
    k = box / max(sym.size)
    sym = sym.resize((max(1, round(sym.width * k)), max(1, round(sym.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(sym, ((size - sym.width) // 2, (size - sym.height) // 2))
    return out


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    for w, h in PANEL_SIZES:
        panel(w, h).save(ART / f"panel-{w}.png", optimize=True)
    for s in MARK_SIZES:
        mark(s, False).save(ART / f"mark-{s}.png", optimize=True)
        mark(s, True).save(ART / f"mark-dark-{s}.png", optimize=True)
    print("wrote", sorted(p.name for p in ART.glob("*.png")))


if __name__ == "__main__":
    main()
