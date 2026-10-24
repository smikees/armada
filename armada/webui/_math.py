"""Protect explicit TeX spans before the shared safe Markdown parser touches them."""
import html
import re

# Skip Markdown literals and destinations. No math is interpreted inside code or URLs.
_PARTS = re.compile(
    r'(?P<code>^[ \t]*```[^\n]*\n[\s\S]*?(?:^[ \t]*```[^\n]*(?:\n|$)|\Z)|`[^`\n]+`)'
    r'|(?P<link>\[[^\]\n]+\]\((?:[^()\n]|\([^()\n]*\))*\))'
    r'|(?P<display>(?<!\\)\\\[(?:(?!\\\[)[\s\S]){0,16000}?(?<!\\)\\\]'
    r'|(?<![\\$])\$\$(?:(?!\$\$)[\s\S]){0,16000}?(?<!\\)\$\$)'
    r'|(?P<inline>(?<!\\)\\\((?:(?!\\\()[^\n]){0,16000}?(?<!\\)\\\))'
    r'|(?P<dollar>(?<![\\$\w])\$(?![\s$])'
    r'(?!\d(?![^\n$]*[\\^_=+*/]))[^\n$]+?(?<![\\\s])\$(?![\d$]))', re.M)


def protect(text):
    """Return Markdown plus a restoration function; source HTML remains escaped later.

    Single dollars are conservative because financial prose commonly contains several prices.
    Numeric expressions should use explicit delimiters unless they contain TeX or operators.
    """
    spans = []
    text = text.replace('\x02', '').replace('\x03', '')

    def stash(match):
        kind = match.lastgroup
        if kind in ('code', 'link'):
            return match[0]
        source = match[0]
        tex = source[1:-1] if kind == 'dollar' else source[2:-2]
        if len(tex) > 16000:
            return source
        if kind == 'dollar' and tex[:1].isdigit() and not re.search(r'[\\^_=+*/]', tex):
            return source
        spans.append((source, tex, kind == 'display'))
        return f'\x02M{len(spans)-1}\x03'

    protected = _PARTS.sub(stash, text)

    def restore(rendered):
        def span(match):
            source, tex, display = spans[int(match[1])]
            return (f'<span class="mc-math{" is-display" if display else ""}" '
                    f'data-tex="{html.escape(tex, quote=True)}">{html.escape(source)}</span>')
        return re.sub(r'\x02M(\d+)\x03', span, rendered)

    return protected, restore
