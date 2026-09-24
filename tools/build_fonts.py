#!/usr/bin/env python3
"""Build the selectable app fonts: subset web fonts + static/fonts.css (v0.99.62).

    python tools/build_fonts.py "D:\\Work\\Fonts"

Temporary feature (Settings → App → Appearance → Fonts), to become part of themes/skins. Six
families, each usable as the body face or the heading face. The point of generating the CSS rather
than writing it is that fonts differ a lot in width: Montserrat at the same pixel size runs 17%
wider than Barlow, and 47% wider than Barlow Condensed in the heading role. Swapped naively,
labels overflow buttons, tabs wrap and pills break.

So every family gets two alias faces — "ARMADA Body <Name>" and "ARMADA Heading <Name>" — each with a
measured `size-adjust`:

- mostly **width-matched** to the design font for that role (Barlow for body at 400, Barlow
  Condensed for headings at 600), measured on a sample of the app's own words, so text takes the
  same room and nothing overflows;
- blended 30% toward **x-height-matched**, so a narrow font doesn't get blown up until its
  lowercase towers over everything else;
- capped so a face is never more than 8% wider than the design font.

Line metrics (ascent/descent/line gap) are pinned to the design font's, divided by the size-adjust
(the overrides are scaled by it), so the baseline sits where it did and buttons, pills and rows
keep their height whatever the face.

Each font's OFL licence is copied beside it, as the SIL Open Font License asks.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "armada" / "webui" / "static" / "fonts"
CSS = ROOT / "armada" / "webui" / "static" / "fonts.css"
WEIGHTS = (400, 500, 600, 700)
UNICODES = ("U+0020-007E,U+00A0-024F,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2190-21FF,"
            "U+2212,U+2215,U+2248,U+2260,U+2264-2265")
SAMPLE = ("The quick brown fox jumps over the lazy dog. Overview Ministers Goals Jobs Inbox Memory "
          "Capabilities Artefacts Settings Daily brief weekdays 14:00 Run now Save changes Agent memory "
          "Realm memory 0123456789 Warren Marcus Aristotle what happened, what you expected, what "
          "happened instead.")
WIDTH_WEIGHT = 0.7          # the rest goes to x-height
MAX_WIDER = 1.08

# slug: (label, folder, {weight: file or ("VAR", file)})
def _static(folder, stem):
    names = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}
    return {w: f"{folder}/{stem}-{n}.ttf" for w, n in names.items()}


FAMILIES = {
    "barlow": ("Barlow", "Barlow", _static("Barlow", "Barlow")),
    "barlow-condensed": ("Barlow Condensed", "Barlow_Condensed", _static("Barlow_Condensed", "BarlowCondensed")),
    "montserrat": ("Montserrat", "Montserrat", _static("Montserrat/static", "Montserrat")),
    "nunito-sans": ("Nunito Sans", "Nunito_Sans",
                    {w: ("VAR", "Nunito_Sans/NunitoSans-VariableFont_YTLC,opsz,wdth,wght.ttf") for w in WEIGHTS}),
    "quicksand": ("Quicksand", "Quicksand", _static("Quicksand/static", "Quicksand")),
    "roboto": ("Roboto", "Roboto", _static("Roboto/static", "Roboto")),
}
ROLES = {"body": ("barlow", 400), "heading": ("barlow-condensed", 600)}


def _load(src: Path, spec, weight: int) -> TTFont:
    if isinstance(spec, tuple):
        f = TTFont(src / spec[1])
        axes = {a.axisTag: a for a in f["fvar"].axes}
        loc = {"wght": weight}
        if "opsz" in axes:
            loc["opsz"] = 12
        if "wdth" in axes:
            loc["wdth"] = 100
        for tag, a in axes.items():
            loc.setdefault(tag, a.defaultValue)
        return instancer.instantiateVariableFont(f, loc)
    return TTFont(src / spec)


def _metrics(f: TTFont) -> dict:
    upm = f["head"].unitsPerEm
    cmap, hmtx = f.getBestCmap(), f["hmtx"]
    width = sum(hmtx[cmap[ord(c)]][0] for c in SAMPLE if ord(c) in cmap) / upm
    hh = f["hhea"]
    return {"width": width, "xh": f["OS/2"].sxHeight / upm,
            "asc": hh.ascent / upm, "desc": -hh.descent / upm, "gap": hh.lineGap / upm}


def _woff2(f: TTFont, dest: Path) -> None:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=subset.parse_unicodes(UNICODES))
    sub.subset(f)
    f.flavor = "woff2"
    f.save(dest)


def main(src_dir: str) -> None:
    src = Path(src_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    metrics = {}
    for slug, (label, folder, files) in FAMILIES.items():
        for w in WEIGHTS:
            f = _load(src, files[w], w)
            if w in (400, 600):
                metrics[(slug, w)] = _metrics(f)
            dest = OUT / f"{slug}-{w}.woff2"
            if not dest.exists():                 # the shipped Barlow files stay byte-identical
                _woff2(f, dest)
        lic = src / folder / "OFL.txt"
        if lic.exists():
            shutil.copyfile(lic, OUT / f"OFL-{slug}.txt")

    rules = ["/* Generated by tools/build_fonts.py — do not edit by hand. See that file for why. */"]
    table = []
    for role, (design, dw) in ROLES.items():
        d = metrics[(design, dw)]
        for slug, (label, _folder, _files) in FAMILIES.items():
            m = metrics[(slug, dw)]
            wr, xr = d["width"] / m["width"], d["xh"] / m["xh"]
            s = (wr ** WIDTH_WEIGHT) * (xr ** (1 - WIDTH_WEIGHT))
            s = min(s, MAX_WIDER * wr)            # never more than 8% wider than the design font
            if slug == design:
                s = 1.0
            asc, desc, gap = d["asc"] / s, d["desc"] / s, d["gap"] / s
            fam = f"ARMADA {role.title()} {label}"
            table.append((role, slug, round(s * 100, 1)))
            for w in WEIGHTS:
                rules.append(
                    f'@font-face{{font-family:"{fam}";src:url(/static/fonts/{slug}-{w}.woff2) format("woff2");'
                    f"font-weight:{w};font-style:normal;font-display:block;size-adjust:{s * 100:.1f}%;"
                    f"ascent-override:{asc * 100:.1f}%;descent-override:{desc * 100:.1f}%;"
                    f"line-gap-override:{gap * 100:.1f}%}}")
    CSS.write_text("\n".join(rules) + "\n", encoding="utf-8")
    for role, slug, pct in table:
        print(f"{role:8} {slug:18} size-adjust {pct:5.1f}%")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"D:\Work\Fonts")
