"""Hard-wrapped Markdown lists.

Documents written by hand wrap at column 95, so a list item routinely spans two or three source
lines with the remainder indented under it. The renderer took only the marker line as the item and
let the rest fall through to the paragraph branch, which produced two visible faults on the same
text: a bullet showing half a sentence with the other half sitting below it as loose prose, and —
because that stray paragraph ended the list run — every numbered item starting a fresh <ol>, so a
five-step list read "1. 1. 1. 1. 1.".
"""
from armada.webui._base import _md

WRAPPED_OL = """\
1. **The daily brief.** One document, every weekday: what changed, what it means, the single thing
   most worth his attention today, and every decision that is overdue or urgent. Built from
   canonical state, never from memory or impression.
2. **The decisions ledger.** Every open question Mihai owes an answer to, with its deadline and
   what happens if it passes.
3. **Cabinet coordination.** You know what each minister is for.
"""

WRAPPED_UL = """\
- **No sulking and no status.** Rome gossiped that Agrippa withdrew to Mytilene because a younger
  man was favoured; the story is probably false, but the pattern is real and it is banned.
- **No empire-building.** You coordinate the Cabinet; you do not accumulate it.
"""


def test_a_wrapped_ordered_list_is_one_list():
    html = _md(WRAPPED_OL)
    assert html.count("<ol") == 1, "each item was starting its own list, so all were numbered 1"
    assert html.count("<li>") == 3


def test_the_continuation_stays_inside_its_item():
    html = _md(WRAPPED_OL)
    first = html.split("<li>")[1].split("</li>")[0]
    assert "canonical state, never from memory or impression." in first
    assert "<p>" not in html.split("<ol")[1].split("</ol>")[0], "continuation leaked into a paragraph"


def test_wrapped_bullets_fold_too():
    html = _md(WRAPPED_UL)
    assert html.count("<ul>") == 1 and html.count("<li>") == 2
    assert "the pattern is real and it is banned." in html.split("<li>")[1]


def test_wrapping_does_not_swallow_the_space_between_lines():
    """Joining without a space would give 'younger man' as 'youngerman'."""
    assert "a younger man was favoured" in _md(WRAPPED_UL)


def test_a_blank_line_still_ends_the_list():
    html = _md("- one\n- two\n\nA new paragraph entirely.\n")
    assert html.count("<li>") == 2
    assert "<p>A new paragraph entirely.</p>" in html


def test_a_heading_ends_the_list():
    html = _md("- one\n## Next section\n")
    assert "<li>one</li>" in html and "<h4>Next section</h4>" in html


def test_a_list_of_the_other_kind_ends_the_list():
    html = _md("- bullet\n1. number\n")
    assert "<ul><li>bullet</li></ul>" in html
    assert "<li>number</li>" in html and html.count("<ol") == 1


def test_an_ordered_list_that_does_not_start_at_one_says_so():
    html = _md("3. third\n4. fourth\n")
    assert '<ol start="3">' in html


def test_a_list_starting_at_one_needs_no_start_attribute():
    assert _md("1. first\n2. second\n").startswith("<ol><li>")


def test_inline_markup_survives_the_fold():
    html = _md("- **Bold lead.** and the rest\n  continues *here* with `code`.\n")
    assert "<strong>Bold lead.</strong>" in html
    assert "<em>here</em>" in html and "<code>code</code>" in html


def test_a_fence_after_a_list_is_not_folded_into_it():
    html = _md("- one\n```\nnot a list item\n```\n")
    assert "<li>one</li>" in html
    assert "not a list item" in html.split("<pre")[1]


def test_the_renderer_still_escapes_everything_it_folds():
    html = _md("- start\n  <script>alert(1)</script>\n")
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
