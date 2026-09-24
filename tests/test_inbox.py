"""Agent-to-agent delegation.

Most of these guard the three ways this feature could hurt: spending quota to discover an empty
inbox, two agents looping forever, and a restart replaying a task that already ran.
"""
import datetime as dt
import json

import pytest

from armada import inbox


@pytest.fixture
def realm(tmp_path):
    def _mk(agents=("galen", "steve", "marcus"), realm_cfg=None, agent_cfg=None):
        (tmp_path / "realm.json").write_text(
            json.dumps({"name": "t", "inbox": realm_cfg or {}}), encoding="utf-8")
        for a in agents:
            d = tmp_path / "agents" / a
            d.mkdir(parents=True, exist_ok=True)
            cfg = {"display": a.title(), "is_coordinator": a == "marcus"}
            cfg.update((agent_cfg or {}).get(a, {}))
            (d / "agent.json").write_text(json.dumps(cfg), encoding="utf-8")
        return tmp_path
    return _mk


# ---- the per-agent master switch ---------------------------------------------------------------

def test_agent_to_agent_is_on_by_default(realm):
    r = realm()
    assert inbox.agent_enabled(r, "steve") is True


def test_switching_an_agent_off_stops_mail_in_both_directions(realm):
    """Off means out of the network, not merely deaf to it — the label says communication, so it
    would be a nasty surprise if a switched-off agent still handed work to teammates."""
    r = realm(agent_cfg={"steve": {"inbox": {"enabled": False}}})
    inbound = inbox.send(r, "galen", "steve", "do a thing")
    assert not inbound["ok"] and inbound["reason"] == "refused"
    outbound = inbox.send(r, "steve", "galen", "do a thing")
    assert not outbound["ok"] and outbound["reason"] == "refused"
    assert not inbox.has_mail(r, "steve")


def test_a_switched_off_agent_is_never_due_and_refuses_at_pickup(realm):
    """Agents write inbox files directly, so the switch has to hold at pickup too — not only in
    send(), which isn't the only way a message can appear."""
    r = realm(agent_cfg={"steve": {"inbox": {"cadence": "minute", "enabled": False}}})
    assert inbox.cadence(r, "steve") == "off"
    assert inbox.due(r, "steve") is False
    ok, why = inbox.screen(r, "steve", {"from": "galen", "ask": "hand-placed task", "hops": 1})
    assert ok is False and "switched off" in why


def test_nobody_is_read_as_the_switch_being_off(realm):
    """'Nobody' said exactly what the switch now says, so it's no longer offered — but realms
    configured before the switch existed still have it saved, and it must keep working AND show up
    as 'off' rather than as an on switch that silently refuses everything."""
    r = realm(agent_cfg={"steve": {"inbox": {"accepts": "nobody"}}})
    assert inbox.agent_enabled(r, "steve") is False
    assert not inbox.send(r, "galen", "steve", "do a thing")["ok"]


def test_a_realm_wide_nobody_reads_as_the_realm_switch_being_off(realm):
    r = realm(realm_cfg={"accepts": "nobody"})
    assert inbox.enabled(r) is False


def test_nobody_is_still_enforced_but_no_longer_offered():
    assert "nobody" in inbox.ACCEPTS, "hand-edited configs and old realms still need it honoured"
    assert "nobody" not in inbox.ACCEPTS_CHOICES, "two controls for one decision is how UIs lie"
    assert set(inbox.ACCEPTS_CHOICES) < set(inbox.ACCEPTS)


def test_the_switch_does_not_erase_the_settings_beneath_it(realm):
    """Greyed out, not cleared: switching back on must restore what was chosen, not reset to
    inherit. The stored cadence stays on disk; only the effective value changes."""
    r = realm(agent_cfg={"steve": {"inbox": {"cadence": "hour", "accepts": "coordinator",
                                             "enabled": False}}})
    assert inbox._agent_cfg(r, "steve")["cadence"] == "hour"
    cfg = json.loads((r / "agents" / "steve" / "agent.json").read_text(encoding="utf-8"))
    cfg["inbox"].pop("enabled")
    (r / "agents" / "steve" / "agent.json").write_text(json.dumps(cfg), encoding="utf-8")
    assert inbox.cadence(r, "steve") == "hour"
    assert inbox.accepts_from(r, "steve") == "coordinator"


# ---- sending ----------------------------------------------------------------------------------

def test_a_task_reaches_the_recipients_inbox(realm):
    r = realm()
    sent = inbox.send(r, "galen", "steve", "add the Fitbit Air to the daily price check")
    assert sent["ok"]
    waiting = inbox._list(r, "steve", inbox.PENDING)
    assert len(waiting) == 1 and waiting[0]["from"] == "galen"
    assert inbox.has_mail(r, "steve") and not inbox.has_mail(r, "galen")


def test_an_agent_cannot_task_itself(realm):
    assert inbox.send(realm(), "steve", "steve", "do a thing")["reason"] == "self"


def test_unknown_recipient_is_refused(realm):
    assert inbox.send(realm(), "galen", "nobody-here", "x")["reason"] == "unknown"


def test_empty_ask_is_refused(realm):
    assert inbox.send(realm(), "galen", "steve", "   ")["reason"] == "empty"


def test_realm_switch_turns_the_whole_feature_off(realm):
    r = realm(realm_cfg={"enabled": False})
    assert inbox.enabled(r) is False
    assert inbox.send(r, "galen", "steve", "x")["reason"] == "disabled"


# ---- loop protection ---------------------------------------------------------------------------

def test_delegation_chains_are_bounded(realm):
    """Two agents answering each other is an unbounded bill — the chain has to die somewhere."""
    r = realm()
    assert inbox.send(r, "galen", "steve", "x", hops=inbox._MAX_HOPS)["reason"] == "hops"


def test_identical_asks_collapse(realm):
    r = realm()
    assert inbox.send(r, "galen", "steve", "add the Fitbit Air")["ok"]
    dup = inbox.send(r, "galen", "steve", "  Add   the FITBIT air ")   # same ask, noisier
    assert dup["reason"] == "duplicate"


def test_a_different_ask_from_the_same_sender_still_gets_through(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "add the Fitbit Air")
    assert inbox.send(r, "galen", "steve", "also add the Oura ring")["ok"]


def test_screen_rejects_an_over_long_chain_written_by_hand(realm):
    """Agents write inbox files directly, so the rules must hold at pickup, not just at send."""
    r = realm()
    ok, why = inbox.screen(r, "steve", {"from": "galen", "ask": "x", "hops": 99})
    assert ok is False and "chain" in why


def test_screen_enforces_the_hourly_ceiling(realm, monkeypatch):
    r = realm()
    monkeypatch.setattr(inbox, "_ran_last_hour", lambda *a: inbox._MAX_PER_HOUR)
    ok, why = inbox.screen(r, "steve", {"from": "galen", "ask": "x", "hops": 1})
    assert ok is False and "limit" in why


def test_replies_are_never_treated_as_tasks(realm):
    """A reply landing in the sender's box must not start a new chain."""
    ok, _ = inbox.screen(realm(), "galen", {"from": "steve", "ask": "done", "reply": True})
    assert ok is False


# ---- who may assign work -----------------------------------------------------------------------

def test_an_agent_can_refuse_all_delegated_work(realm):
    r = realm(agent_cfg={"steve": {"inbox": {"accepts": "nobody"}}})
    assert inbox.send(r, "galen", "steve", "x")["reason"] == "refused"


def test_coordinator_only_blocks_peers_but_allows_the_coordinator(realm):
    r = realm(agent_cfg={"steve": {"inbox": {"accepts": "coordinator"}}})
    assert inbox.send(r, "galen", "steve", "peer ask")["reason"] == "refused"
    assert inbox.send(r, "marcus", "steve", "boss ask")["ok"] is True


# ---- cadence ------------------------------------------------------------------------------------

def test_cadence_falls_back_realm_then_default(realm):
    assert inbox.cadence(realm(), "steve") == inbox.DEFAULT_CADENCE
    assert inbox.cadence(realm(realm_cfg={"cadence": "day"}), "steve") == "day"
    r = realm(realm_cfg={"cadence": "day"}, agent_cfg={"steve": {"inbox": {"cadence": "minute"}}})
    assert inbox.cadence(r, "steve") == "minute" and inbox.cadence(r, "galen") == "day"


def test_cadence_off_means_never_due(realm):
    r = realm(agent_cfg={"steve": {"inbox": {"cadence": "off"}}})
    assert inbox.due(r, "steve") is False


def test_due_respects_the_interval(realm):
    r = realm(agent_cfg={"steve": {"inbox": {"cadence": "hour"}}})
    assert inbox.due(r, "steve") is True          # never checked
    inbox.mark_checked(r, "steve")
    assert inbox.due(r, "steve") is False         # just checked
    marker = r / "agents" / "steve" / "inbox" / ".last"
    marker.write_text((dt.datetime.now().astimezone() - dt.timedelta(hours=2)).isoformat(), encoding="utf-8")
    assert inbox.due(r, "steve") is True


def test_checking_an_inbox_costs_nothing(realm):
    """has_mail is the whole poll: a directory listing, no engine, no tokens. This is what makes a
    one-minute cadence sane rather than eleven thousand agent runs a day."""
    import inspect
    import re
    src = inspect.getsource(inbox.has_mail)
    code = re.sub(r'""".*?"""', "", src, flags=re.S)      # the docstring says "no engine"
    for expensive in ("engine", "run_job", "subprocess", "eng."):
        assert expensive not in code


# ---- exactly once --------------------------------------------------------------------------------

def test_claiming_is_atomic_and_cannot_double_run(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "x")
    msg = inbox._list(r, "steve", inbox.PENDING)[0]
    first = inbox.claim(r, "steve", msg)
    assert first is not None and first["state"] == inbox.RUNNING
    assert inbox.claim(r, "steve", msg) is None, "a second claim must fail, not replay the task"
    assert not inbox.has_mail(r, "steve")


def test_completing_files_the_task_and_replies_to_the_sender(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "add the Fitbit Air")
    msg = inbox.claim(r, "steve", inbox._list(r, "steve", inbox.PENDING)[0])
    inbox.complete(r, "steve", msg, True, "added to the price watch list")
    done = inbox._list(r, "steve", inbox.DONE)
    assert len(done) == 1 and done[0]["ok"] is True
    back = inbox._list(r, "galen", inbox.DONE)
    assert back and back[0]["reply"] is True and "completed" in back[0]["ask"]


def test_a_failure_is_reported_back_not_swallowed(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "impossible thing")
    msg = inbox.claim(r, "steve", inbox._list(r, "steve", inbox.PENDING)[0])
    inbox.complete(r, "steve", msg, False, "no such product feed")
    back = inbox._list(r, "galen", inbox.DONE)
    assert back and back[0]["ok"] is False and "could not" in back[0]["ask"]


def test_batch_is_capped_per_pass(realm):
    r = realm()
    for i in range(10):
        inbox.send(r, "galen", "steve", f"task {i}")
    assert len(inbox.next_batch(r, "steve")) <= inbox._MAX_PER_RUN


# ---- the prompt ----------------------------------------------------------------------------------

# ---- the inbox page ------------------------------------------------------------------------------

def test_messages_split_into_waiting_recent_and_archive(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "still waiting")
    # one handled just now, one handled long ago
    inbox.send(r, "galen", "steve", "handled now")
    m = inbox.claim(r, "steve", [x for x in inbox._list(r, "steve", inbox.PENDING)
                                 if x["ask"] == "handled now"][0])
    inbox.complete(r, "steve", m, True, "done")
    old = r / "agents" / "steve" / "inbox" / "done" / "ancient.json"
    old.write_text(json.dumps({
        "id": "ancient", "from": "galen", "to": "steve", "ask": "long ago", "state": "done",
        "ok": True, "created": "2020-01-01T00:00:00+00:00",
        "finished": "2020-01-01T00:00:00+00:00"}), encoding="utf-8")
    data = inbox.all_messages(r, recent_hours=24)
    assert [x["ask"] for x in data["waiting"]] == ["still waiting"]
    assert "handled now" in [x["ask"] for x in data["recent"]]
    assert "long ago" in [x["ask"] for x in data["archive"]]


def test_marking_unread_puts_it_back_to_be_run_again(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "do it again")
    m = inbox.claim(r, "steve", inbox._list(r, "steve", inbox.PENDING)[0])
    inbox.complete(r, "steve", m, True, "first attempt")
    assert inbox.requeue(r, "steve", m["id"])["ok"] is True
    again = inbox._list(r, "steve", inbox.PENDING)
    assert len(again) == 1 and again[0]["ask"] == "do it again"
    # the previous outcome is cleared so it reads as genuinely unhandled
    assert "ok" not in again[0] and "detail" not in again[0]
    assert inbox.has_mail(r, "steve")


def test_requeue_keeps_the_hop_count(realm):
    """Re-running must not become a way around the chain limit."""
    r = realm()
    inbox.send(r, "galen", "steve", "deep task", hops=2)
    m = inbox.claim(r, "steve", inbox._list(r, "steve", inbox.PENDING)[0])
    inbox.complete(r, "steve", m, True, "")
    inbox.requeue(r, "steve", m["id"])
    assert inbox._list(r, "steve", inbox.PENDING)[0]["hops"] == 2


def test_a_reply_cannot_be_requeued(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "x")
    m = inbox.claim(r, "steve", inbox._list(r, "steve", inbox.PENDING)[0])
    inbox.complete(r, "steve", m, True, "")
    reply = inbox._list(r, "galen", inbox.DONE)[0]
    assert inbox.requeue(r, "galen", reply["id"])["ok"] is False


def test_already_waiting_cannot_be_requeued(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "x")
    mid = inbox._list(r, "steve", inbox.PENDING)[0]["id"]
    assert inbox.requeue(r, "steve", mid)["ok"] is False


def test_deleting_removes_the_message(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "unwanted")
    mid = inbox._list(r, "steve", inbox.PENDING)[0]["id"]
    assert inbox.delete(r, "steve", mid)["ok"] is True
    assert inbox._list(r, "steve", inbox.PENDING) == []


def test_acting_on_a_vanished_message_fails_cleanly(realm):
    r = realm()
    assert inbox.delete(r, "steve", "nope")["ok"] is False
    assert inbox.requeue(r, "steve", "nope")["ok"] is False


def test_a_reply_is_paired_with_the_message_it_answers(realm):
    r = realm()
    inbox.send(r, "galen", "steve", "add the Fitbit Air")
    m = inbox.claim(r, "steve", inbox._list(r, "steve", inbox.PENDING)[0])
    inbox.complete(r, "steve", m, True, "added")
    reply = inbox._list(r, "galen", inbox.DONE)[0]
    assert reply["parent"] == m["id"]
    assert inbox.parent_id(reply) == m["id"]
    assert inbox.parent_id(m) == "", "an ordinary message has no parent"


def test_parent_falls_back_to_the_id_convention():
    """Replies written before the parent field existed must still pair up."""
    assert inbox.parent_id({"reply": True, "id": "reply-abc123"}) == "abc123"


def test_threading_puts_each_reply_under_its_own_message():
    a = {"id": "a", "ask": "task a"}
    b = {"id": "b", "ask": "task b"}
    ra = {"id": "reply-a", "reply": True, "parent": "a", "ask": "done a"}
    rb = {"id": "reply-b", "reply": True, "parent": "b", "ask": "done b"}
    out = inbox.threaded([a, b, rb, ra])          # deliberately out of order
    assert [(m["id"], d) for m, d in out] == [("a", 0), ("reply-a", 1), ("b", 0), ("reply-b", 1)]


def test_an_orphan_reply_is_still_shown(realm):
    """If the original was filtered out, deleted, or is older than this section, the reply must
    still appear rather than silently vanishing."""
    out = inbox.threaded([{"id": "reply-gone", "reply": True, "parent": "gone", "ask": "x"}])
    assert [(m["id"], d) for m, d in out] == [("reply-gone", 0)]


def test_threading_keeps_every_message(realm):
    items = [{"id": "a"}, {"id": "reply-a", "reply": True, "parent": "a"}, {"id": "b"}]
    assert len(inbox.threaded(items)) == len(items)


def test_replies_render_indented():
    from pathlib import Path
    pages = (Path(inbox.__file__).parent / "webui" / "pages.py").read_text(encoding="utf-8")
    block = pages[pages.index("def inbox_view"):pages.index("def _sec_head")]
    assert "_inbox.threaded(items)" in block and "_inbox.threaded(arch)" in block
    assert "margin-left:26px" in block


def test_agent_and_realm_views_share_one_renderer():
    """The per-agent Inbox tab is the realm view scoped, not a second implementation that can
    drift — the old agent tab read loose .md files and would now always be empty."""
    from pathlib import Path
    src = Path(inbox.__file__).parent / "webui" / "agentframe.py"
    txt = src.read_text(encoding="utf-8")
    assert "_pages.inbox_view(realm, realm_root, agent_id=a.id)" in txt
    assert "_inbox_msgs(realm_root, a.id)" not in txt, "the markdown placeholder must be gone"


def test_inbox_view_filters_and_archive_search_exist():
    from pathlib import Path
    pages = (Path(inbox.__file__).parent / "webui" / "pages.py").read_text(encoding="utf-8")
    block = pages[pages.index("def inbox_view"):pages.index("def _sec_head")]
    for want in ('id="ib-from"', 'id="ib-to"', 'id="ib-status"', 'id="ib-arch-q"',
                 'data-from=', 'data-to=', 'data-status=', 'data-search='):
        assert want in block, f"the inbox view is missing {want}"
    # the archive renders even when empty — a section that appears only once populated reads as
    # a missing feature rather than an empty one
    assert "Nothing archived yet" in block


def test_modals_are_app_native_everywhere():
    """ARMADA never uses the browser's confirm()/alert() — they look foreign and can't be styled."""
    import re
    from pathlib import Path
    web = Path(inbox.__file__).parent / "webui"
    block = (web / "static" / "js" / "inbox.js").read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", block)
    assert not re.search(r"(?<![\w.])(confirm|alert)\(", code), "inbox must use mcConfirm"
    assert "window.mcConfirm(" in block
    # the shared dialog is loaded on every page, so nothing needs a local fallback
    assert "CONFIRM_JS" in (web / "layout.py").read_text(encoding="utf-8")


def test_inbox_cards_collapse_by_default():
    """A delegated task can carry long instructions; unrolling all of them by default buries the
    list. Title shows, the rest is one click away."""
    from pathlib import Path
    pages = (Path(inbox.__file__).parent / "webui" / "pages.py").read_text(encoding="utf-8")
    block = pages[pages.index("def inbox_view"):pages.index("def _sec_head")]
    assert "<details class=\"mc-frame mc-inbox-msg\"" in block
    assert "mc-inbox-body" in block
    # a single long line still expands: the title elides it, so the full text must be reachable
    assert "truncated or len(stripped) > len(first)" in block
    # and the expansion is verbatim — an expansion that still truncates is worse than none
    assert "{E(stripped)}" in block and "ask[:4000]" not in block
    # the status label is "Pending" now, not "Waiting" (prose elsewhere may still say waiting)
    assert '"Running" if running else "Pending"' in block
    assert '>Waiting<' not in block
    assert "Processed in the last 24h" in block


def test_agent_view_drops_the_to_filter():
    """Every message on an agent's own tab already concerns that agent, so a 'to' filter would be
    a control that does nothing."""
    from pathlib import Path
    pages = (Path(inbox.__file__).parent / "webui" / "pages.py").read_text(encoding="utf-8")
    block = pages[pages.index("def inbox_view"):pages.index("def _sec_head")]
    assert 'to_filter = ("" if agent_id else' in block
    assert '"From anyone" if agent_id' in block


def test_the_prompt_is_self_contained(realm):
    """The inbox thread accumulates unrelated asks for months; compaction would otherwise blend a
    fitness tracker into a pricing question."""
    p = inbox.prompt_for({"from": "galen", "ask": "add the Fitbit Air",
                          "context": "we chose it over the Oura"})
    assert "galen" in p and "add the Fitbit Air" in p and "we chose it over the Oura" in p
    assert "approval" in p.lower()      # tells them to propose rather than act unilaterally
