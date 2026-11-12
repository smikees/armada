"""Realm-bound destinations and shared state for independent thread views."""
from pathlib import Path
import hashlib
import json
from urllib.parse import urlencode

from . import reader, util
from .request_context import RealmContext, bind_content_html
from .view_cache import ViewCache, history_stamp

_renders = ViewCache(limit=32)


# Only first-party companion requests opt in to an explicit realm after the main
# cockpit switches. Ordinary stale pages still fail closed. These are intent
# markers, not credentials; all requests still require the app's local session.
COMPANION_GET = frozenset({
    "/api/thread-state", "/api/thread-turns", "/api/thread-metrics",
    "/api/thread-rail", "/api/agent-activity", "/api/chat-stop",
})
COMPANION_POST = frozenset({
    "/api/thread-read",
    "/api/voice-start", "/api/voice-state", "/api/voice-stop",
    "/api/chat-stream", "/api/chat-steer", "/api/thread-truncate", "/api/thread-action",
    "/api/open-file", "/api/reveal", "/api/render-md",
})


def target(root, agent, thread, *, _previews=None):
    """Validate an existing thread without silently falling back to main."""
    from .webui.threadsview import _ordered_threads, _thread_title
    agent = util.safe_seg(agent, "agent")
    thread = util.safe_seg(thread, "thread")
    context = RealmContext.capture(root)
    realm = reader.roster(context.root)
    a = next((a for a in realm.agents if a.id == agent), None)
    if a is None:
        raise util.StateError("This agent is no longer available.")
    ad = Path(context.root) / 'agents' / agent
    summaries = {}
    names, meta = _ordered_threads(ad, summaries=summaries)
    if thread not in names:
        raise util.StateError("This thread is no longer available. It may have been archived or deleted.")
    if _previews is not None:
        from .threads import Thread
        from .webui.threadsview import _thread_summary
        for name in names:
            value = summaries[name] if name in summaries else _thread_summary(Thread(ad, name))
            _previews[name] = value[0]
    route = "/thread-window?" + urlencode({"agent": agent, "thread": thread, "_realm": context.realm_id})
    return context, a, _thread_title(meta, thread), route


def state(root, agent, thread, revision=""):
    """Canonical conversation snapshot, shared by the cockpit, widget and companion."""
    from .execution import ACTIVE_RUNS, RUNS_LOCK
    from .webui.threadsview import _render_turns, thread_metrics, _turn_snapshot
    from .threads import Thread
    previews = {}
    context, a, title, _ = target(root, agent, thread, _previews=previews)
    with RUNS_LOCK:
        from . import steering
        runs = [run for run in ACTIVE_RUNS.values()
                if run.context.realm.realm_id == context.realm_id
                and run.context.agent == agent and run.context.thread == thread
                and getattr(run, 'kind', '') != 'voice_audio']
        payload = {"title": title, "run_id": runs[0].context.run_id if runs else "",
                   "stopping": any(run.cancelled for run in runs),
                   "steerable": len(runs) == 1 and steering.available(runs[0])}
    from . import voice
    call = voice.current(root, agent, thread)
    payload['voice'] = call.snapshot() if call and not call.finished.is_set() else None
    from .webui.threadsview import _portrait, _user_avatar, _chat_running, _agent_model_label
    from . import model
    th = Thread(Path(root) / 'agents' / agent, thread)
    def stamp():
        # Read dynamic presentation inputs each time, including marker PID liveness.
        speech = call.snapshot() if call and not call.finished.is_set() else None
        label = _agent_model_label(root, agent)
        return (history_stamp(th, progress=True), a.display, a.is_coordinator,
                _portrait(root, a, 28), _user_avatar(root, 28),
                _chat_running(root, agent, thread), json.dumps(speech, sort_keys=True),
                label, model.context_window_tokens(label))
    def build():
        snapshot = _turn_snapshot(root, agent, thread, th)
        return (bind_content_html(_render_turns(root, a, thread, state=snapshot), context),
                thread_metrics(root, agent, thread, thread=th, snapshot=snapshot[:2]),
                [{key: item[key] for key in ('id', 'status', 'error') if key in item}
                 for item in steering.receipts(snapshot[1])])
    html, metrics, delivered = _renders.read((context.realm_id, agent, thread), stamp, build)
    payload['metrics'] = dict(metrics)
    payload['steering'] = delivered
    digest = hashlib.sha256((html + json.dumps(payload, sort_keys=True)).encode("utf-8")).hexdigest()
    payload["revision"] = digest
    if revision != digest:
        payload["html"] = html
    # A different thread's preview can change without rerendering this conversation.
    payload['previews'] = previews
    return payload
