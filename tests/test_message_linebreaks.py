"""Sent composer text retains line breaks in the shared main/detached renderer."""
from armada.webui._base import _md
from armada.webui.threadsview import _turn


def test_pasted_bullet_points_stay_separate_in_a_sent_message():
    text='• No, the put expired. I lost $2k plus the $200 premium.\n• We are one hour into the session.\nPlease close this session.'
    html=_turn('user',text,'',0,True,'a','main','Ada',False)
    assert '<ul><li>No, the put expired.' in html
    assert '</li><li>We are one hour into the session.<br>Please close this session.</li></ul>' in html
    assert text in html, 'the raw copy/edit template retains the exact source'


def test_plain_lines_and_crlf_are_preserved_without_changing_document_wrapping():
    text='First line\r\nSecond line\n\nNext paragraph'
    assert _md(text,preserve_breaks=True)=='<p>First line<br>Second line</p><p>Next paragraph</p>'
    assert _md(text)=='<p>First line Second line</p><p>Next paragraph</p>'


def test_markdown_lists_and_code_keep_structure_and_escape_untrusted_html():
    text='- **First**\n  continuation\n- Second\n\n```text\n• literal\n<script>x</script>\n```'
    html=_md(text,preserve_breaks=True)
    assert '<li><strong>First</strong><br>continuation</li><li>Second</li>' in html
    assert '<code>• literal\n&lt;script&gt;x&lt;/script&gt;</code>' in html
    assert '<script>' not in html


def test_math_newlines_are_not_changed_into_html_inside_tex():
    html=_md('A formula:\n\\[x_1\n+ x_2\\]\nThen text.',preserve_breaks=True)
    assert 'data-tex="x_1\n+ x_2"' in html
    assert '<br>' in html
