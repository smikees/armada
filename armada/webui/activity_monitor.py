"""Dashboard activity drawn from local state; no provider calls or mark-as-read effects."""
from pathlib import Path
from urllib.parse import urlencode,quote
from .. import clock,status,run_summary
from ._base import E
from .agentbits import _agent_busy,_has_pending_proposals,_thread_meta
import logging
log=logging.getLogger(__name__)


def content(realm,root):
    try:
        return _content(realm,root)
    except (OSError,ValueError,TypeError):
        log.warning('Could not read activity monitor records',exc_info=True)
        return '<p role="status">Activity records are unavailable. Open the agent or Jobs page to check.</p>'


def _content(realm,root):
    groups={name:[] for name in ('Working','Unread replies','Needs input','Failed replies')}
    from .. import capabilities
    request_agents={aid for aid,_,_,_ in capabilities.iter_requests(root)}
    for agent in realm.agents:
        href=f'/agent/{quote(agent.id,safe="")}/threads'
        if _agent_busy(root,agent.id):
            groups['Working'].append((href,agent.display))
        if _has_pending_proposals(root,agent.id):
            groups['Needs input'].append((f'/agent/{quote(agent.id,safe="")}/jobs',agent.display))
        if agent.id in request_agents:
            groups['Needs input'].append((f'/agent/{quote(agent.id,safe="")}/skills',agent.display+' · capability request'))
        meta=_thread_meta(Path(root)/'agents'/agent.id)
        unread_map=meta.get('unread') or {}
        titles=meta.get('titles') or {}
        if not isinstance(unread_map,dict) or not isinstance(titles,dict):
            raise ValueError('Invalid thread activity metadata')
        for thread,unread in unread_map.items():
            if unread:
                title=titles.get(thread) or thread.title()
                groups['Unread replies'].append((href+'?'+urlencode({'thread':thread}),f'{agent.display} · {title}'))
        latest,*_=run_summary.totals(Path(root)/'agents'/agent.id,clock.today().isoformat())
        for task,(_,outcome) in latest.items():
            if task.startswith('chat:') and status.is_bad(status.normalize(outcome)):
                thread=task[5:]
                groups['Failed replies'].append((href+'?'+urlencode({'thread':thread}),f'{agent.display} · {thread.title()}'))
    blocks=[]
    for title,rows in groups.items():
        links=''.join(f'<li><a href="{E(href)}">{E(label)}</a></li>' for href,label in rows)
        blocks.append(f'<section><h3>{title} <span>{len(rows)}</span></h3>'+
                      (f'<ul>{links}</ul>' if rows else '<p class="mc-activity-empty">None</p>')+'</section>')
    from .attention import panel
    return '<div class="mc-activity-groups">'+''.join(blocks)+'</div>'+panel(realm,root).replace('<details ','<details open ',1)


def widget(realm,root,section=False):
    from .widgets import _wid_header
    from ..assets import js
    return ('<div class="mc-widget mc-activity-monitor" style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
            +_wid_header('Activity monitor',widget_id='activity',chrome=not section)
            +'<div class="mc-scroll" data-activity-monitor style="flex:1;min-height:0;overflow:auto;padding:12px 14px">'
            +content(realm,root)+'</div></div>'+js('activity_monitor'))
