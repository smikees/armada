# KaTeX 0.19.1

MIT-licensed browser renderer and fonts, bundled for offline use. See LICENSE.
Source package: https://registry.npmjs.org/katex/-/katex-0.19.1.tgz
Verified npm SHA-512 integrity:
`jG8uKntjSEcm2EpQOh0XturpPuuC9r3Sq5HLHdsFdWZT27E672SF19QEi+of0/YeOy15lDgRhKvr5614uRrEfA==`

Only dist/katex.min.js, dist/katex.min.css, dist/fonts and LICENSE are shipped.
ARMADA's shared Markdown parser recognizes TeX spans before escaping and formatting text.
Its local math.js renders those spans with trust disabled, isolated macros and bounded expansion
and dimensions. No conversation text is sent to a CDN. Unsupported TeX falls back to escaped source.
Update this pinned directory and its provenance together when upgrading KaTeX.
Also update the pinned version query in armada/assets.py so cached browser assets refresh.
