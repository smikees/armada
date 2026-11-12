"""Dashboard activity drawn from local state; no provider calls or mark-as-read effects."""
from pathlib import Path
from urllib.parse import urlencode,quote
from .. import clock,status,run_summary
from ._base import E
from .agentbits import _agent_busy,_has_pending_proposals,_thread_meta,_portrait
import logging
log=logging.getLogger(__name__)


def content(realm,root):
    try:
        return _content(realm,root)
    except (OSError,ValueError,TypeError):
        log.warning('Could not read activity monitor records',exc_info=True)
        return '<p role="status">Activity records are unavailable. Open the agent or Jobs page to check.</p>'


def _content(realm,root):
    groups={name:{} for name in ('Working','Unread replies','Needs input','Failed replies')}
    def add(group,agent,href,detail):
        # One portrait per agent per row; keep multiple threads/requests in its tooltip.
        row=groups[group].setdefault(agent.id,(agent,href,[]))
        if detail:
            row[2].append(detail)
    from .. import capabilities
    request_agents={aid for aid,_,_,_ in capabilities.iter_requests(root)}
    for agent in realm.agents:
        href=f'/agent/{quote(agent.id,safe="")}/threads'
        if _agent_busy(root,agent.id):
            add('Working',agent,href,'')
        if _has_pending_proposals(root,agent.id):
            add('Needs input',agent,f'/agent/{quote(agent.id,safe="")}/jobs','Job proposal')
        if agent.id in request_agents:
            add('Needs input',agent,f'/agent/{quote(agent.id,safe="")}/skills','Capability request')
        meta=_thread_meta(Path(root)/'agents'/agent.id)
        unread_map=meta.get('unread') or {}
        titles=meta.get('titles') or {}
        if not isinstance(unread_map,dict) or not isinstance(titles,dict):
            raise ValueError('Invalid thread activity metadata')
        for thread,unread in unread_map.items():
            if unread:
                title=titles.get(thread) or thread.title()
                add('Unread replies',agent,href+'?'+urlencode({'thread':thread}),str(title))
        latest,*_=run_summary.totals(Path(root)/'agents'/agent.id,clock.today().isoformat())
        for task,(_,outcome) in latest.items():
            if task.startswith('chat:') and status.is_bad(status.normalize(outcome)):
                thread=task[5:]
                add('Failed replies',agent,href+'?'+urlencode({'thread':thread}),str(titles.get(thread) or thread.title()))
    blocks=[]
    for title,rows in groups.items():
        key=title.lower().replace(' ','-')
        links=''
        for agent,href,details in rows.values():
            label=f'{agent.display} · {title}'+(' · '+', '.join(details) if details else '')
            links+=(f'<li><a class="mc-activity-avatar" href="{E(href)}" title="{E(label)}" '
                    f'aria-label="{E(label)}" data-activity-key="{E(key+":"+agent.id)}">'
                    f'{_portrait(root,agent,36,dot=True)}</a></li>')
        blocks.append(f'<section data-activity-group="{key}"><h3>{title} <span>{len(rows)}</span></h3>'+
                      (f'<ul>{links}</ul>' if rows else '<p class="mc-activity-empty">None</p>')+'</section>')
    from .attention import panel
    return '<div class="mc-activity-groups">'+''.join(blocks)+'</div>'+panel(realm,root,collapsible=False)


def widget(realm,root,section=False):
    from .widgets import _wid_header
    from ..assets import js
    from ..icons import _ICON_REFRESH
    refresh=('<button type="button" class="mc-iconbtn" data-activity-refresh '
             'aria-label="Refresh activity" title="Refresh activity">'+_ICON_REFRESH+'</button>')
    return ('<div class="mc-widget mc-activity-monitor" style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
            +_wid_header('Activity monitor',right=refresh,widget_id='activity',chrome=not section)
            +'<span class="mc-activity-feedback" data-activity-feedback role="status" aria-live="polite"></span>'
            +'<div class="mc-scroll" data-activity-monitor style="flex:1;min-height:0;overflow:auto;padding:12px 14px">'
            +content(realm,root)+'</div></div>'+js('activity_monitor'))
