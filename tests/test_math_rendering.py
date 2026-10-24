"""TeX is protected before Markdown, without turning financial prose or code into math."""
from html.parser import HTMLParser

import pytest

from armada.webui._base import _md


class Formulas(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tex = []
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if 'data-tex' in attrs:
            self.tex.append(attrs['data-tex'])


EXAMPLE = r'\underbrace{\$200}_{\text{premium}} + \underbrace{\$4{,}000}_{\text{shares now worth}} -\underbrace{\$5{,}000}_{\text{paid on assignment}} = -\$800.'


def test_screenshot_underbraces_preserve_exact_tex():
    result = _md('Correct — an $800 loss.\n\n\\[\n'+EXAMPLE+'\n\\]')
    assert Formulas(result).tex == ['\n'+EXAMPLE+'\n']
    assert '<em>' not in result and 'is-display' in result
    assert '$800 loss.' in result


@pytest.mark.parametrize('source,expected', [
    (r'Use \(x_i^2 + y_i^2\) here.', ['x_i^2 + y_i^2']),
    ('$$x_1 = 2\ny_2 = 4$$', ['x_1 = 2\ny_2 = 4']),
    ('$x^2$ and $2^n$', ['x^2', '2^n']),
    ('Pay $50 per share, strike $55, premium $2. Total $800.', []),
    ('Pay $50, then compute $x^2$.', ['x^2']),
    (r'`\[x_1\]` and `$$x$$`', []),
    ('```tex\n\\[x_1\\]\n```', []),
    (r'[formula](https://example.com/\(x\))', []),
    (r'An incomplete \[x_1', []),
])
def test_delimiters_code_currency_and_links(source, expected):
    assert Formulas(_md(source)).tex == expected


def test_math_cannot_inject_html_or_forge_placeholders():
    source = r'\[\text{" onmouseover="alert(1)"}<script>alert(1)</script>\]'
    result = _md(source+'\x02M999\x03')
    assert Formulas(result).tex == [source[2:-2]]
    assert 'script' not in Formulas(result).tags
    assert 'onmouseover="alert' not in result


def test_math_pipes_and_stars_are_not_markdown_table_or_emphasis():
    result = _md('| Formula |\n| --- |\n| \\(a|b * c_i\\) |')
    assert Formulas(result).tex == ['a|b * c_i']
    assert result.count('<td>') == 1


def test_oversized_math_keeps_readable_source():
    result = _md('\\['+'x'*16001+'\\]')
    assert not Formulas(result).tex
