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
    groups={name:{} for name in ('Working','Queued','Unread replies','Needs input','Failed replies')}
    from .. import execution_admission
    from .. import job_waits
    prerequisite_waits = job_waits.state(root)
    from .. import job_triggers, util
    requested = [r for r in job_triggers.history(root) if r['state']=='queued' and util.pid_alive(r.get('owner_pid',0))]
    live=[row for row in execution_admission.snapshot() if Path(row['root']).resolve()==Path(root).resolve()]
    def add(group,agent,href,detail):
        # One portrait per agent per row; keep multiple threads/requests in its tooltip.
        row=groups[group].setdefault(agent.id,(agent,href,[]))
        if detail:
            row[2].append(detail)
    from .. import capabilities,questions
    request_agents={aid for aid,_,_,_ in capabilities.iter_requests(root)}
    for agent in realm.agents:
        href=f'/agent/{quote(agent.id,safe="")}/threads'
        waiting=questions.waiting(root,agent.id)
        tickets=[row for row in live if row['agent']==agent.id]
        for row in requested:
            if row['agent']==agent.id:
                add('Queued',agent,f'/agent/{quote(agent.id,safe="")}/jobs?'+urlencode({'job':row['job']}),row.get('wait_reason') or row['reason'])
        for row in prerequisite_waits.values():
            if row.get('agent') == agent.id and row.get('state') == 'waiting':
                add('Queued', agent, f'/agent/{quote(agent.id,safe="")}/jobs?' + urlencode({'job':row['job']}), row.get('reason', 'Waiting for prerequisites'))
        queued=[row for row in tickets if row['state']=='queued']
        for row in queued:
            from ..job_history import JOB_PREFIX
            target=(f'/agent/{quote(agent.id,safe="")}/jobs?'+urlencode({'job':row['thread'][len(JOB_PREFIX):]})
                    if row['thread'].startswith(JOB_PREFIX) else href+'?'+urlencode({'thread':row['thread']}))
            add('Queued',agent,target,row.get('queue_reason') or 'Waiting for execution capacity')
        if (any(row['state']=='running' for row in tickets) or (not tickets and _agent_busy(root,agent.id))) and not waiting:
            add('Working',agent,href,'')
        for thread in waiting:
            add('Needs input',agent,href+'?'+urlencode({'thread':thread}),'Question awaiting your answer')
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
                    f'{_portrait(root,agent,36,dot=True,dot_state="queued" if title=="Queued" else "")}</a></li>')
        blocks.append(f'<section data-activity-group="{key}"><h3>{title} <span>{len(rows)}</span></h3>'+
                      (f'<ul>{links}</ul>' if rows else '<p class="mc-activity-empty">None</p>')+'</section>')
    from .attention import panel
    from .. import sysjobs
    background=[j for j in sysjobs.status(root) if j['status'] in ('running','queued','held')]
    systems=''.join(f'<li><span><a href="/jobs?tab=system">{E(j["name"])}</a> · '
                    f'{"Interrupted" if j["status"]=="held" else j["status"].title()} — {E(j["detail"])}</span></li>' for j in background)
    for row in live:
        if row['agent']=='system' and row['thread'].startswith('aux-'):
            systems+=f'<li><span>{E(row["provider"].title())} background model call · {E(row["state"].title())}</span></li>'
    if systems:
        blocks.append('<section data-activity-group="system"><h3>System work</h3><ul>'+systems+'</ul></section>')
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
