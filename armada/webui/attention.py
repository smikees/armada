"""Actionable owner summary from local records, without provider probes."""
from .. import capabilities, clock, jobs, status
import logging
from ..util import swallowed
from ._base import E
from .agentbits import _runs
log = logging.getLogger(__name__)


def panel(realm, root, *, collapsible=True):
    rows = []
    today = clock.today().isoformat()
    for agent in realm.agents:
        if agent.record_error or agent.history_errors:
            rows.append((f'/agent/{agent.id}', f'{agent.display}: records need repair; work is held'))
            continue
        for job in agent.jobs:
            if job.record_error:
                rows.append((f'/job/{agent.id}/{job.id}', f'{agent.display} / {job.name}: needs repair'))
        # The date index bounds this read to today, never the lifetime history.
        try:
            failures = sum(1 for run in _runs(root, agent.id, since=today)
                           if str(run.get('ts', ''))[:10] == today and status.is_bad(status.normalize(run.get('status', ''))))
        except (OSError, ValueError, TypeError):
            swallowed(log, 'attention: recent run details unavailable')
            rows.append((f'/agent/{agent.id}/jobs', f'{agent.display}: recent run details unavailable'))
            continue
        if failures:
            rows.append((f'/agent/{agent.id}/jobs', f'{agent.display}: {failures} failed or interrupted runs today'))
    for read, href, label in ((jobs.count_pending, '/jobs', 'job proposals'),
                              (capabilities.count_requests, '/approvals', 'capability requests')):
        try:
            count = read(root)
            if count:
                rows.append((href, f'{count} {label} await your review'))
        except (OSError, ValueError, TypeError):
            swallowed(log, 'attention: review records unavailable')
            rows.append((href, f'Could not read {label}; open the page to check'))
    if not rows:
        if not collapsible:
            return ('<section class="mc-attention-summary"><h3>Needs attention</h3>'
                    '<p>No failed runs today or pending approvals found.</p></section>')
        return ('<div class="mc-attention-summary">Attention: no failed runs today or pending approvals found.</div>')
    tag,heading=('details','summary') if collapsible else ('section','h3')
    return (f'<{tag} class="mc-attention-summary is-active"><{heading}>Needs attention · '
            f'{len(rows)} area{"s" if len(rows) != 1 else ""} to review</{heading}><ul>' +
            ''.join(f'<li><a href="{E(href)}">{E(text)}</a></li>' for href, text in rows) +
            f'</ul><p>Recent failures remain listed for today; this is not a live provider health check.</p></{tag}>')
