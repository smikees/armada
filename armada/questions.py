"""Realm/run-bound question admission and durable owner answers, never tool approval."""
import copy
import datetime
from pathlib import Path
from .threads import Thread


def record(thread,turn,run_id,request):
    public=copy.deepcopy(request)
    public['run_id']=run_id
    def change(message):
        rows=message.setdefault('question_requests',[])
        existing=next((r for r in rows if r['id']==public['id']),None)
        if existing is None:
            if len(rows)>=32:
                raise ValueError('This turn has reached its question limit.')
            public['ts']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
            rows.append(public)
        else:
            existing.update(public)
        return True
    thread._store.update_turn_request(turn,change)


def pending(active):
    from .engine.questions import QuestionControl
    control=getattr(getattr(active,'process',None),'questions',None)
    return [r for r in control.snapshot() if r['status'] in ('pending','queued')] if isinstance(control,QuestionControl) and not active.cancelled else []


def waiting(root,agent,thread=None):
    from .execution import ACTIVE_RUNS,RUNS_LOCK
    from .engine.questions import QuestionControl
    from .request_context import RealmContext
    with RUNS_LOCK:
        candidates=[]
        for active in ACTIVE_RUNS.values():
            if active.context.agent!=agent or active.cancelled or thread is not None and active.context.thread!=thread:
                continue
            control=getattr(active.process,'questions',None)
            if isinstance(control,QuestionControl) and control.waiting:
                candidates.append((active.context.realm.realm_id,active.context.thread))
    if not candidates:
        return []
    realm_id=RealmContext.capture(root).realm_id
    return [name for identity,name in candidates if identity==realm_id]


def answer(root,agent,thread,run_id,identity,answers,cancelled=False):
    from .execution import ACTIVE_RUNS,RUNS_LOCK
    from .thread_windows import target
    context,_,_,_=target(root,agent,thread)
    if not isinstance(run_id,str) or not run_id or not isinstance(identity,str) or not identity:
        raise ValueError('An answer requires the exact active run and question ID.')
    if not isinstance(cancelled,bool):
        raise ValueError('Invalid question cancellation.')
    with RUNS_LOCK:
        active=ACTIVE_RUNS.get((context.realm_id,run_id))
        if not active or active.cancelled or active.context.agent!=agent or active.context.thread!=thread:
            raise ValueError('This question belongs to a run that has already ended. Your answer was not sent.')
        control=getattr(active.process,'questions',None)
        if control is None:
            raise ValueError('This run cannot accept question answers.')
        th=Thread(Path(context.root)/'agents'/agent,thread)
        # Do not deliver an answer whose question cannot be retained in history.
        found=any(r.get('id')==identity and r.get('run_id')==run_id for m in th._messages() for r in m.get('question_requests',[]))
        if not found:
            raise ValueError('The original question is no longer available. Your answer was not sent.')
        return control.answer(identity,answers,cancelled,
            persist=lambda row:record(th,active.steering_turn,run_id,row))
