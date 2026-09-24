"""Auto-naming a new thread from the first prompt (heuristic title derivation)."""
from armada.routes._shared import _derive_title


def test_basic_command():
    assert _derive_title("Create a daily job called Test Job 8") == "Create a daily job called Test Job 8"


def test_first_line_only():
    assert _derive_title("Summarize this report\n\nlots of extra context here") == "Summarize this report"


def test_strips_markdown_and_quotes():
    assert _derive_title('- **"Revert the filter changes"**') == "Revert the filter changes"


def test_truncates_long_to_word_boundary():
    t = _derive_title("Please revert all of the filter edits because the jobs that were supposed to fire did not")
    assert len(t) <= 49 and t.endswith("…") and "  " not in t


def test_sentence_cases_first_letter():
    assert _derive_title("what does this cost?").startswith("What does this cost")


def test_empty_and_whitespace():
    assert _derive_title("") == ""
    assert _derive_title("   \n  ") == ""
