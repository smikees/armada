"""The capability-request approval message, and the link it points at.

Caught live: the notification linked to /capabilities, which 404s — the Capabilities page is served
at /skills. A dead link in a notification is the kind of thing tests never see because nobody
asserts on hrefs, and users hit on the first real request.
"""
import inspect
import json

from armada import runner


def test_the_note_leads_with_the_reason():
    """'Warren wants the filesystem extension' is not a decision. What for is."""
    title, body = runner._cap_request_note("Warren", "finance", {
        "capability": "filesystem", "name": "filesystem", "kind": "extensions",
        "reason": "to read the quarterly CSVs you asked about", "thread": "taxes"})
    assert "Warren" in title
    assert "quarterly CSVs" in body
    assert "filesystem" in body
    assert "taxes" in body


def test_a_request_with_no_reason_says_so():
    _, body = runner._cap_request_note("Warren", "finance",
                                       {"capability": "filesystem", "name": "filesystem"})
    assert "(no reason given)" in body, "an empty line would read as a formatting glitch"


def test_the_note_says_what_approving_would_do():
    _, body = runner._cap_request_note("Galen", "health",
                                       {"capability": "x", "name": "X", "reason": "r"})
    assert "next run" in body


def test_the_kind_is_singular_and_readable():
    _, body = runner._cap_request_note("Ray", "strategy",
                                       {"capability": "x", "name": "X", "kind": "extensions"})
    assert "extension" in body


def test_the_notification_links_to_a_route_that_exists():
    """Pins the fix: /capabilities is not a route, /skills is the Capabilities page."""
    src = inspect.getsource(runner._sync_cap_requests)
    assert 'href="/skills"' in src
    from armada import serve
    routes = set(getattr(serve, "GET_ROUTES", {}) or {})
    if not routes:                     # route table lives on the handler class
        routes = set(getattr(getattr(serve, "Handler", object), "GET_ROUTES", {}) or {})
    if routes:
        assert "/skills" in routes and "/capabilities" not in routes


def test_a_request_is_only_notified_once(tmp_path):
    """The file survives until approved or rejected, so an un-stamped request would re-notify on
    every subsequent turn."""
    from armada import capabilities as C
    r = tmp_path / "realm"
    (r / "agents" / "warren").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"toolkit": {
        "extensions": [{"id": "filesystem", "name": "filesystem"}]}}), encoding="utf-8")
    (r / "agents" / "warren" / "agent.json").write_text(json.dumps({"id": "warren"}), encoding="utf-8")
    C.request(r, "warren", "filesystem", "reason", thread="main")

    sent = []
    orig = runner._notify
    try:
        runner._notify = lambda *a, **k: sent.append(a)
        runner._sync_cap_requests(r, "warren", "main")
        runner._sync_cap_requests(r, "warren", "main")
    finally:
        runner._notify = orig
    assert len(sent) == 1, f"notified {len(sent)} times for one request"


def test_the_thread_is_stamped_when_the_agent_left_it_out(tmp_path):
    """An agent rarely knows its own thread name; the turn does."""
    from armada import capabilities as C
    r = tmp_path / "realm"
    (r / "agents" / "warren").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"toolkit": {
        "extensions": [{"id": "filesystem", "name": "filesystem"}]}}), encoding="utf-8")
    (r / "agents" / "warren" / "agent.json").write_text(json.dumps({"id": "warren"}), encoding="utf-8")
    C.request(r, "warren", "filesystem", "reason")          # no thread
    orig = runner._notify
    try:
        runner._notify = lambda *a, **k: None
        runner._sync_cap_requests(r, "warren", "taxes")
    finally:
        runner._notify = orig
    req = json.loads((C.requests_dir(r, "warren") / "filesystem.json").read_text(encoding="utf-8"))
    assert req["thread"] == "taxes"
