"""Markdown metadata keeps its existing flat format across realm and memory readers."""
import pytest

from armada import memory, reader
from armada.util import parse_frontmatter


@pytest.mark.parametrize('parse', [parse_frontmatter, memory._frontmatter, reader._frontmatter])
@pytest.mark.parametrize('text,expected', [
    ('', ({}, '')),
    ('ordinary text\n', ({}, 'ordinary text\n')),
    ('---\ntitle: "A note"\n---\nBody\n', ({'title': 'A note'}, 'Body\n')),
    ('---\n # ignored: value\nurl: https://example.invalid/a:b\n---\nBody',
     ({'url': 'https://example.invalid/a:b'}, 'Body')),
    ('---\ntitle: first\ninvalid line\ntitle: second\n---\nBody', ({'title': 'second'}, 'Body')),
    ("---\nflag: true\ncount: 2\ntitle: 'quoted'\n---\nBody",
     ({'flag': 'true', 'count': '2', 'title': "'quoted'"}, 'Body')),
    ('---\r\ntitle: Windows\r\n---\r\nBody\r\n', ({'title': 'Windows'}, 'Body\r\n')),
    ('---\ntitle: incomplete\n---', ({}, '---\ntitle: incomplete\n---')),
])
def test_flat_metadata_and_body_are_preserved(parse, text, expected):
    assert parse(text) == expected
