"""Subset the owner's IBM Plex fonts into self-hosted WOFF2, with their OFL licenses.

python tools/build_armada_ii_fonts.py D:\\Work\\db\\Armada\\Fonts
Unlike the legacy interchangeable faces, Plex uses its natural width in both roles.
"""
from pathlib import Path
import shutil
import sys

from fontTools.ttLib import TTFont
from build_fonts import OUT, CSS, WEIGHTS, _woff2, _metrics


def main(root):
    source = Path(root) / 'IBM_Plex_Mono,IBM_Plex_Sans,Inter'
    names = {400:'Regular',500:'Medium',600:'SemiBold',700:'Bold'}
    rules = []
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, label, folder in [('ibm-plex-sans','IBM Plex Sans','IBM_Plex_Sans'),
                               ('ibm-plex-mono','IBM Plex Mono','IBM_Plex_Mono')]:
        base = source / folder
        stem = label.replace(' ', '')
        shutil.copyfile(base / 'OFL.txt', OUT / f'OFL-{slug}.txt')
        for weight in WEIGHTS:
            font = TTFont(base / ('static' if slug.endswith('sans') else '') / f'{stem}-{names[weight]}.ttf')
            metrics = _metrics(font)
            _woff2(font, OUT / f'{slug}-{weight}.woff2')
            families = [f'ARMADA Body {label}', f'ARMADA Heading {label}'] if slug.endswith('sans') else [label]
            for family in families:
                rules.append(f'@font-face{{font-family:"{family}";src:url(/static/fonts/{slug}-{weight}.woff2) format("woff2");'
                             f'font-weight:{weight};font-style:normal;font-display:block;size-adjust:100.0%;'
                             f'ascent-override:{metrics["asc"]*100:.1f}%;descent-override:{metrics["desc"]*100:.1f}%;'
                             f'line-gap-override:{metrics["gap"]*100:.1f}%}}')
    existing = [line for line in CSS.read_text(encoding='utf-8').splitlines() if 'IBM Plex' not in line]
    CSS.write_text('\n'.join(existing + rules) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
