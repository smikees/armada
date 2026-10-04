# Preview asset manifest

Reviewed 2026-10-03. the maintainer approved publication on 2026-10-03; these assets are now live.
The user rejected the generated compositions and prohibited invented application UI
and example data. No generated or sourced raster assets are required by this revision.

| Asset | Source and treatment | Verification |
| --- | --- | --- |
| `assets/armada-logo.svg` | Supplied original ARMADA wordmark SVG; original file preserved. HTML SVG viewport `1682 5125 5136 750` omits page whitespace. | Byte-identical SHA-256: `D2EF800F7EC58FE724B99234707ED3B85462B03279CF9A9B2B02FDB605EB11C3`. Complete wordmark visible in desktop and mobile captures. |
| `assets/armada-symbol.svg` | Supplied original ARMADA symbol SVG; original file preserved. HTML SVG viewport `3575 5125 1360 750` omits page whitespace. | Byte-identical SHA-256: `9229D7013DABFF17FCECC60EB13DFA2FA7BCD505B8675E7DD6173EF52A652D8B`. Complete symbol visible in mobile footer. |
| `assets/fonts/barlow-400.woff2` and `barlow-500.woff2` | Existing application fonts from `armada/webui/static/fonts`; body and medium-weight text. | Both files present with WOFF2 signatures. `OFL-barlow.txt` included. |
| `assets/fonts/barlow-condensed-600.woff2` | Existing application font from `armada/webui/static/fonts`; headings. | File present with WOFF2 signature. `OFL-barlow-condensed.txt` included. |
| Download icon | Simple semantic inline SVG path in `index.html`. | Decorative icon is hidden from assistive technology; button text remains HTML. |

Both font notices identify the Barlow Project Authors and SIL Open Font License 1.1.
All three font files and both notices match the existing application files by SHA-256.
Supplied logo artwork is used as directed by the user; this review does not establish
broader redistribution rights. All copy, controls, rules and surfaces remain HTML/CSS.

## Deliberately empty production inventory

- Generated illustrations, photography, textures, product mockups and app screenshots: none.
- Generated composition images shipped in this preview: none.
- Missing media required by the current text-led composition: none.
- Prompts, embedded generation metadata and raster crop variants: not applicable.

## Visual inspection

Reviewed `build/website-review/desktop.png` and `mobile.png`. Neither supplied logo
shows obvious clipping in its visible placement. The desktop capture ends through
the beta note and does not show the footer, so it does not verify the desktop footer
symbol. The mobile capture includes the footer. No illustrative replacements or
invented app UI appear in either capture.
