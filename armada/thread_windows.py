"""Realm-bound destinations and shared state for independent thread views."""
from pathlib import Path
import hashlib
import json
from urllib.parse import urlencode

from . import reader, util
from .request_context import RealmContext, bind_content_html


# Only first-party companion requests opt in to an explicit realm after the main
# cockpit switches. Ordinary stale pages still fail closed. These are intent
# markers, not credentials; all requests still require the app's local session.
COMPANION_GET = frozenset({
    "/api/thread-state", "/api/thread-turns", "/api/thread-metrics",
    "/api/thread-rail", "/api/agent-activity", "/api/chat-stop",
})
COMPANION_POST = frozenset({
    "/api/chat-stream", "/api/thread-truncate", "/api/thread-action",
    "/api/open-file", "/api/reveal", "/api/render-md",
})


def target(root, agent, thread):
    """Validate an existing thread without silently falling back to main."""
    from .webui.threadsview import _ordered_threads, _thread_title
    agent = util.safe_seg(agent, "agent")
    thread = util.safe_seg(thread, "thread")
    context = RealmContext.capture(root)
    realm = reader.read(context.root)
    a = next((a for a in realm.agents if a.id == agent), None)
    if a is None:
        raise util.StateError("This agent is no longer available.")
    names, meta = _ordered_threads(Path(context.root) / "agents" / agent)
    if thread not in names:
        raise util.StateError("This thread is no longer available. It may have been archived or deleted.")
    route = "/thread-window?" + urlencode({"agent": agent, "thread": thread, "_realm": context.realm_id})
    return context, a, _thread_title(meta, thread), route


def state(root, agent, thread, revision=""):
    """Canonical conversation snapshot, shared by the cockpit, widget and companion."""
    from .execution import ACTIVE_RUNS, RUNS_LOCK
    from .webui.threadsview import _render_turns, thread_metrics
    context, a, title, _ = target(root, agent, thread)
    html = bind_content_html(_render_turns(root, a, thread), context)
    with RUNS_LOCK:
        runs = [run for run in ACTIVE_RUNS.values()
                if run.context.realm.realm_id == context.realm_id
                and run.context.agent == agent and run.context.thread == thread]
        payload = {"title": title, "run_id": runs[0].context.run_id if runs else "",
                   "stopping": any(run.cancelled for run in runs)}
    payload["metrics"] = thread_metrics(root, agent, thread)
    digest = hashlib.sha256((html + json.dumps(payload, sort_keys=True)).encode("utf-8")).hexdigest()
    payload["revision"] = digest
    if revision != digest:
        payload["html"] = html
    return payload
