"""Owner review preserves full values, safe formatting and approval boundaries."""
from html.parser import HTMLParser

import pytest

from armada import jobs, reader, run_policy, util
from armada.webui.agentcommon import _job_proposals_block
from armada.webui.job_proposals import comparison, value_html


def text(markup):
    class Reader(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    parser = Reader()
    parser.feed(markup)
    return ''.join(parser.parts)


def change(before, after, **kwargs):
    return {'field': 'prompt', 'before': before, 'after': after,
            'added': False, 'removed': False, **kwargs}


def test_formatted_comparison_marks_only_changed_words_and_preserves_newlines():
    old, new, note = comparison(change('## Report\n\nRead **five** files.\nKeep this line.\n\n- Save `report.md`',
                                      '## Report\n\nRead **six** files.\nKeep this line.\n\n- Save `report.md`'))
    assert '<strong><del>five</del></strong>' in old
    assert '<strong><ins>six</ins></strong>' in new
    assert '<br>' in new and '<ul>' in new and '<code>report.md</code>' in new
    assert '<del>Read' not in old and not note
    assert '\\n' not in text(new)


@pytest.mark.parametrize('old,new', [
    ('[Report](https://old.example)', '[Report](https://new.example)'),
    ('[Report](https://old.example) today', '[Report](https://new.example) tomorrow'),
    ('**Same text**', '*Same text*'),
])
def test_formatting_and_hidden_link_changes_remain_reviewable(old, new):
    before, after, note = comparison(change(old, new))
    assert note and '<pre' in before and '<pre' in after
    assert text(before) == old and text(after) == new
    assert '<del>' in before or '<ins>' in after


def test_proposal_text_cannot_inject_html_or_script():
    old, new, _ = comparison(change('A & B', '<img src=x onerror=alert(1)>\n<script>bad()</script>'))
    assert '<img' not in new and '<script' not in new
    assert '<img src=x onerror=alert(1)>' in text(new)
    assert text(old) == 'A & B'


def test_added_removed_empty_and_structured_values_are_distinct():
    old, new, _ = comparison(change(None, False, field='allow_tools', added=True))
    assert 'Not set' in text(old) and text(new) == 'No'
    old, new, _ = comparison(change('', None, field='run', removed=True))
    assert text(old) == 'Empty' and text(new) == 'Not set'
    assert value_html(None) != value_html(None, absent=True)
    assert '\n' in text(value_html({'required_outputs': ['report.md']}))
    old, new, note = comparison(change(None, 'Not set', field='run', added=True))
    assert not note and '<del>' in old and '<ins>' in new
    old, new, note = comparison(change(None, 'None', field='run'))
    assert 'type changed' in note and text(old) == 'null' and text(new) == '"None"'


def test_large_repetitive_values_preserve_all_text():
    before = 'old value ' * 5000
    after = 'new value ' * 5000
    old, new, _ = comparison(change(before, after, field='run'))
    assert text(old) == before and text(new) == after
    assert '<del>' in old and '<ins>' in new


@pytest.fixture
def proposal(tmp_path):
    root = tmp_path/'realm'
    util.write_json_atomic(root/'realm.json', {'name': 'Synthetic review'})
    util.write_json_atomic(root/'agents/a/agent.json', {'id': 'a', 'display': 'Ada'})
    saved = {'id': 'daily', 'name': 'Daily review', 'kind': 'agent', 'prompt': 'Read **five** files.',
             'allow_tools': True, 'cron': '*/15 15-16 * * 1-5'}
    path = root/'agents/a/jobs/daily.json'
    util.write_json_atomic(path, saved)
    run_policy.seal_job(root, 'a', saved)
    pending = path.parent/'_pending/daily.json'
    util.write_json_atomic(pending, {**saved, 'prompt': 'Read **six** files.'})
    return root, path, pending


def test_existing_proposal_is_collapsed_has_one_comparison_and_does_not_mutate(proposal):
    root, path, pending = proposal
    before = path.read_bytes(), pending.read_bytes(), run_policy._path().read_bytes()
    markup = _job_proposals_block(reader.read_native(root), root)
    assert '<details class="mc-prop"' in markup and '<details open' not in markup
    assert 'mc-prop-preview' not in markup and '<table class="mc-propdiff"' not in markup
    assert markup.count('<del>five</del>') == markup.count('<ins>six</ins>') == 1
    assert 'Approved value' in markup and 'Proposed value' in markup
    assert 'weekdays every 15 min, 15:00–16:45' in markup
    assert 'data-review-token="' in markup and 'mc-propapprove' in markup
    assert before == (path.read_bytes(), pending.read_bytes(), run_policy._path().read_bytes())


def test_new_proposal_shows_complete_prompt_once(proposal):
    root, path, pending = proposal
    path.unlink()
    job = util.read_json_state(pending)
    job['prompt'] = 'Full paragraph.\n\n' * 100 + '**Unique ending**'
    util.write_json_atomic(pending, job)
    markup = _job_proposals_block(reader.read_native(root), root)
    assert 'New job' in markup and 'mc-prop-preview' in markup
    assert markup.count('<strong>Unique ending</strong>') == 1
    assert 'Approved value' not in markup


def test_saved_baseline_is_labelled_when_approval_snapshot_unavailable(proposal):
    root, _, _ = proposal
    util.write_json_atomic(run_policy._path(), {})
    markup = _job_proposals_block(reader.read_native(root), root)
    assert 'Saved value' in markup and 'older approval snapshot' in markup

