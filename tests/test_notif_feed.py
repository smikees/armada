"""The in-app notification feed: the archive behind the bell.

Contract: everything ARMADA announces is recorded, whether or not it also raised a desktop
notification — so turning toasts off quiets the desktop without losing the history.
"""
import json

import pytest

from armada import notify


@pytest.fixture
def realm(tmp_path, monkeypatch):
    monkeypatch.setattr(notify, "_send", lambda *a: None)
    monkeypatch.setattr(notify.os, "name", "nt")
    notify._recent.clear()
    (tmp_path / "realm.json").write_text(json.dumps({"name": "t"}), encoding="utf-8")
    return tmp_path


def test_emit_records_and_toasts_an_interrupting_event(realm):
    r = notify.emit(realm, "job_failed", "Warren: job failed", "weekly scan")
    assert r["recorded"] is True and r["toasted"] is True
    items = notify.feed(realm)
    assert items[0]["title"] == "Warren: job failed" and items[0]["event"] == "job_failed"


def test_feed_only_events_are_recorded_but_never_toasted(realm):
    r = notify.emit(realm, "update_available", "2 capability updates available")
    assert r["recorded"] is True
    assert r["toasted"] is False, "feed-only events must not interrupt the desktop"
    assert notify.feed(realm)[0]["event"] == "update_available"


def test_history_is_kept_even_when_desktop_notifications_are_off(realm, monkeypatch):
    """Switching toasts off should quiet the desktop, not erase the record."""
    monkeypatch.setattr(notify, "channel_enabled", lambda c: c != "desktop")
    r = notify.emit(realm, "job_finished", "Galen finished a task")
    assert r["toasted"] is False and r["recorded"] is True
    assert len(notify.feed(realm)) == 1


def test_feed_is_newest_first(realm):
    for i in range(3):
        notify.record(realm, "job_started", f"job {i}")
    titles = [i["title"] for i in notify.feed(realm)]
    assert titles == ["job 2", "job 1", "job 0"]


def test_unread_counts_only_entries_after_last_read(realm):
    notify.record(realm, "job_started", "first")
    notify.mark_read(realm)
    assert notify.unread_count(realm) == 0
    notify.record(realm, "job_failed", "second")
    notify.record(realm, "job_failed", "third")
    assert notify.unread_count(realm) == 2
    notify.mark_read(realm)
    assert notify.unread_count(realm) == 0


def test_missing_feed_reads_as_empty(tmp_path):
    assert notify.feed(tmp_path) == []
    assert notify.unread_count(tmp_path) == 0
    assert notify.last_read(tmp_path) == ""


def test_a_torn_line_does_not_lose_the_feed(realm):
    notify.record(realm, "job_started", "good one")
    with (realm / notify._FEED_NAME).open("a", encoding="utf-8") as f:
        f.write("{not json\n")
    notify.record(realm, "job_failed", "later one")
    titles = [i["title"] for i in notify.feed(realm)]
    assert "good one" in titles and "later one" in titles


def test_feed_is_trimmed_so_it_cannot_grow_forever(realm):
    for i in range(notify._FEED_MAX + 80):
        notify.record(realm, "job_started", f"j{i}")
    lines = (realm / notify._FEED_NAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) <= notify._FEED_MAX + 50
    assert notify.feed(realm, limit=1)[0]["title"] == f"j{notify._FEED_MAX + 79}"   # newest kept


def test_record_never_raises_on_an_unwritable_location(monkeypatch, tmp_path):
    monkeypatch.setattr(notify, "_feed_path", lambda r: tmp_path / "no" / "such" / "x.jsonl")

    def boom(*a, **k):
        raise OSError("read-only")
    monkeypatch.setattr(notify.Path, "mkdir", boom)
    assert notify.record(tmp_path, "job_started", "t") is None


def test_emit_without_a_realm_still_does_not_raise():
    assert notify.emit(None, "job_started", "t")["recorded"] is False


def test_every_feed_event_kind_is_declared():
    """The bell renders per-kind icons; an event nobody declared would render as a bare dot."""
    assert set(notify.ALL_EVENTS) == set(notify.EVENTS)
    assert all(notify.ALL_EVENTS.values()), "every event needs a human label"


def test_history_is_kept_for_a_week(realm):
    """Notifications go stale within hours; a week of history is already generous, and a shorter
    window keeps the feed readable without a count cap that would drop today's entries."""
    assert notify.RETAIN_DAYS == 7
    import datetime as dt
    old = (dt.datetime.now().astimezone() - dt.timedelta(days=9)).isoformat(timespec="microseconds")
    recent = (dt.datetime.now().astimezone() - dt.timedelta(days=2)).isoformat(timespec="microseconds")
    p = realm / notify._FEED_NAME
    p.write_text("".join(json.dumps({"ts": t, "event": "job_failed", "title": t[:10]}) + "\n"
                         for t in (old, recent)), encoding="utf-8")
    assert notify.prune(realm) == 1
    left = notify.feed(realm)
    assert len(left) == 1 and left[0]["ts"] == recent


def test_prune_on_an_empty_or_missing_feed_is_harmless(tmp_path):
    assert notify.prune(tmp_path) == 0


def test_job_started_is_off_by_default():
    """It's the bulk of the traffic in a real realm and needs no action — the finish is the news."""
    assert not any(notify.default_matrix()["job_started"].values())


def test_an_unticked_kind_is_skipped_everywhere_including_the_feed(realm):
    """Volume can only be cut if switching a kind off also keeps it out of the bell."""
    (realm / "realm.json").write_text(json.dumps({"notifications": {"matrix": {
        "job_finished": {"inapp": False, "desktop": False, "telegram": False}}}}), encoding="utf-8")
    r = notify.emit(realm, "job_finished", "Galen finished a task")
    assert r["recorded"] is False and r["toasted"] is False
    assert notify.feed(realm) == []


def test_silencing_the_desktop_channel_still_keeps_history(realm, monkeypatch):
    """The other switch means something different — and must keep meaning it."""
    monkeypatch.setattr(notify, "desktop_enabled", lambda: False)
    notify.emit(realm, "job_failed", "Warren: job failed")
    assert len(notify.feed(realm)) == 1


def test_one_events_row_does_not_affect_another(realm):
    (realm / "realm.json").write_text(json.dumps({"notifications": {"matrix": {
        "job_started": {"inapp": False}}}}), encoding="utf-8")
    assert notify.emit(realm, "update_available", "1 update")["recorded"] is True


def test_bell_js_groups_consecutive_repeats():
    from pathlib import Path
    js = (Path(notify.__file__).parent / "webui" / "static" / "js" / "notifbell.js").read_text(encoding="utf-8")
    assert "function group(" in js and "group(items)" in js
    assert "prev.count++" in js


def test_entries_carry_a_destination(realm):
    notify.emit(realm, "approval_needed", "Needs your approval", "x", "/approvals")
    assert notify.feed(realm)[0]["href"] == "/approvals"


@pytest.mark.parametrize("bad", [
    "javascript:alert(1)", "//evil.example/x", "https://evil.example",
    "data:text/html,x", "", None, "   ",
])
def test_offsite_and_script_destinations_are_dropped(realm, bad):
    """Notification text is built from agent and job names, so the destination is untrusted input —
    only a same-origin path may survive."""
    notify.record(realm, "job_failed", "t", "b", bad)
    assert notify.feed(realm)[0]["href"] == ""


def test_same_origin_paths_survive(realm):
    notify.record(realm, "job_finished", "t", "b", "/agent/finance/threads?thread=main")
    assert notify.feed(realm)[0]["href"] == "/agent/finance/threads?thread=main"


def test_runner_builds_a_thread_link_and_escapes_it():
    from armada import runner
    assert runner._thread_href("finance", "main") == "/agent/finance/threads?thread=main"
    # an agent or thread name with a slash or space must not break out of the path
    h = runner._thread_href("a/b", "my thread")
    assert h == "/agent/a%2Fb/threads?thread=my%20thread"
    assert notify._safe_href(h) == h


def test_bell_js_rechecks_destinations():
    from pathlib import Path
    js = (Path(notify.__file__).parent / "webui" / "static" / "js" / "notifbell.js").read_text(encoding="utf-8")
    assert "safeHref" in js and "startsWith('//')" in js


def test_bell_signals_unread_and_rings_on_arrival():
    """A dot for 'something is unread', one short shake when something lands. The shake is keyed on
    the newest timestamp, not the count, so it still fires when one arrives while another is being
    marked read — and so a test notification rings exactly like a real one."""
    from pathlib import Path
    js = (Path(notify.__file__).parent / "webui" / "static" / "js" / "notifbell.js").read_text(encoding="utf-8")
    assert "mc-belldot" in js and "mc-bell-ring" in js
    assert "ringIfNew" in js and "lastSeenTs" in js
    # one unread indicator only — a count badge and a dot in the same corner overlap into a blob
    assert "mc-bellbadge" not in js
    layout = (Path(notify.__file__).parent / "webui" / "layout.py").read_text(encoding="utf-8")
    assert "mc-bellbadge" not in layout
    assert "window.mcBellRefresh" in js, "other pages need a way to make the bell look now"
    css = (Path(notify.__file__).parent / "webui" / "static" / "brand.css").read_text(encoding="utf-8")
    assert "@keyframes mc-bellring" in css
    assert "prefers-reduced-motion" in css, "the shake must be suppressible"


def test_a_test_notification_reaches_the_bell_immediately():
    import inspect
    from pathlib import Path
    from armada import serve
    src = inspect.getsource(serve.Handler._notify_test)
    assert '_n.record(self.realm, "test"' in src      # in-app test writes a real feed entry
    js = (Path(notify.__file__).parent / "webui" / "static" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "window.mcBellRefresh()" in js             # ...and the bell is told to look at once


def test_bell_js_knows_every_event_kind():
    from pathlib import Path
    js = (Path(notify.__file__).parent / "webui" / "static" / "js" / "notifbell.js").read_text(encoding="utf-8")
    for ev in notify.ALL_EVENTS:
        assert ev in js, f"the bell has no icon mapping for {ev}"
