"""Build the composer's two circular markers: python tools/build_list_markers.py.

Requires fonttools and brotli, like the other font builders. These original
outlines share their diameter, advance and centre, unlike the prose fonts'
bullet glyphs. Only U+2022 and U+25E6 are mapped; text and spaces keep the user's
body font. Dimensions are in thousandths of an em and scale with the text.
"""
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen


OUT = Path(__file__).resolve().parents[1] / 'armada/webui/static/fonts/list-markers.woff2'
DIAMETER = 360
ADVANCE = 560
CENTER_Y = 375  # Optically centred on body text, rather than the raised prose bullet baseline.
STROKE = 65


def circle(pen, radius, *, reverse=False):
    """Draw a circular contour; the reverse contour leaves the sub-item hollow."""
    x, y = ADVANCE / 2, CENTER_Y
    k = radius * 0.5522847498
    direction = -1 if reverse else 1
    pen.moveTo((x + radius, y))
    pen.curveTo((x + radius, y + direction*k), (x + k, y + direction*radius), (x, y + direction*radius))
    pen.curveTo((x - k, y + direction*radius), (x - radius, y + direction*k), (x - radius, y))
    pen.curveTo((x - radius, y - direction*k), (x - k, y - direction*radius), (x, y - direction*radius))
    pen.curveTo((x + k, y - direction*radius), (x + radius, y - direction*k), (x + radius, y))
    pen.closePath()


def build():
    glyphs = {'.notdef': TTGlyphPen(None).glyph()}
    for name in ('bullet', 'openbullet'):
        outline = TTGlyphPen(None)
        pen = Cu2QuPen(outline, max_err=0.5, reverse_direction=True)
        circle(pen, DIAMETER / 2)
        if name == 'openbullet':
            circle(pen, DIAMETER / 2 - STROKE, reverse=True)
        glyphs[name] = outline.glyph()
    font = FontBuilder(1000, isTTF=True)
    font.setupGlyphOrder(list(glyphs))
    font.setupCharacterMap({0x2022: 'bullet', 0x25E6: 'openbullet'})
    font.setupGlyf(glyphs)
    font.setupHorizontalMetrics({name: (ADVANCE, 100) for name in glyphs})
    font.setupHorizontalHeader(ascent=1000, descent=-200)
    font.setupNameTable({'familyName': 'Armada List Markers', 'styleName': 'Regular',
                         'uniqueFontIdentifier': 'Armada List Markers 1.0',
                         'fullName': 'Armada List Markers', 'psName': 'ArmadaListMarkers',
                         'version': 'Version 1.0',
                         'licenseDescription': 'PolyForm Noncommercial License 1.0.0; see repository LICENSE.'})
    font.setupOS2(sTypoAscender=1000, sTypoDescender=-200, sTypoLineGap=0,
                  usWinAscent=1000, usWinDescent=200, sxHeight=500, sCapHeight=700)
    font.setupPost()
    # Fixed timestamps make rebuilding the checked-in asset reproducible.
    font.font['head'].created = font.font['head'].modified = 2082844800
    font.font.recalcTimestamp = False
    font.font.flavor = 'woff2'
    font.save(OUT)
    print(OUT)


if __name__ == '__main__':
    build()
