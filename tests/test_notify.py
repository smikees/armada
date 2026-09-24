"""Desktop notifications: opt-outs are honoured and a failure can never reach the caller."""
import json
from pathlib import Path

import pytest

from armada import notify


@pytest.fixture(autouse=True)
def _clear_dedupe():
    notify._recent.clear()
    yield
    notify._recent.clear()


@pytest.fixture
def realm(tmp_path):
    def _mk(cfg=None):
        js = {"name": "t"}
        if cfg is not None:
            js["notifications"] = cfg
        (tmp_path / "realm.json").write_text(json.dumps(js), encoding="utf-8")
        return tmp_path
    return _mk


def test_defaults_interrupt_only_for_things_needing_a_person(realm):
    m = notify.matrix(realm())
    # job starts are the bulk of the traffic and need no action — off on every channel
    assert m["job_started"] == {"inapp": False, "desktop": False, "telegram": False}
    # failures and approvals need a person, so they reach everywhere
    assert all(m["job_failed"].values()) and all(m["approval_needed"].values())
    # a signed-out session halts every agent — it earns an interruption wherever you are
    assert all(m["signed_out"].values())
    # housekeeping news is worth recording, not worth interrupting for
    assert m["update_available"] == {"inapp": True, "desktop": False, "telegram": False}


def test_every_event_declares_a_full_row(realm):
    """A missing channel key would silently read as 'off' and look like a bug in delivery."""
    for ev, meta in notify.EVENTS.items():
        assert meta["label"] and meta["group"] in (notify.AGENTS, notify.SYSTEM)
        assert set(meta["default"]) == set(notify.CHANNELS), f"{ev} is missing a channel default"


def test_legacy_master_switch_still_silences_everything(realm):
    """Settings saved before channels existed must keep meaning what they meant."""
    m = notify.matrix(realm({"enabled": False, "job_started": True}))
    assert all(not any(row.values()) for row in m.values())


def test_legacy_flat_settings_are_read_forward(realm):
    """Before channels, one switch governed both the bell and the desktop — so that's how an old
    saved value is interpreted, rather than silently resetting someone's preferences."""
    m = notify.matrix(realm({"job_finished": False, "job_failed": True}))
    assert m["job_finished"]["inapp"] is False and m["job_finished"]["desktop"] is False
    assert m["job_failed"]["inapp"] is True and m["job_failed"]["desktop"] is True
    # untouched kinds keep their defaults
    assert m["update_available"] == notify.default_matrix()["update_available"]


def test_saved_matrix_wins_over_defaults(realm):
    m = notify.matrix(realm({"matrix": {"job_started": {"inapp": True, "desktop": True}}}))
    assert m["job_started"]["inapp"] is True and m["job_started"]["desktop"] is True
    assert m["job_started"]["telegram"] is False      # unspecified falls back to the default


def test_missing_realm_json_falls_back_to_defaults(tmp_path):
    assert notify.matrix(tmp_path / "nope") == notify.default_matrix()


def test_disabled_event_is_not_dispatched(realm, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "_send", lambda *a: sent.append(a))
    monkeypatch.setattr(notify.os, "name", "nt")
    r = realm({"matrix": {"job_started": {"inapp": False, "desktop": False, "telegram": False}}})
    assert notify.toast("t", "b", realm_root=r, event="job_started") is False
    assert sent == []


def test_duplicate_within_window_is_suppressed(monkeypatch):
    monkeypatch.setattr(notify, "_send", lambda *a: None)
    monkeypatch.setattr(notify.os, "name", "nt")
    assert notify.toast("same", "body") is True
    assert notify.toast("same", "body") is False     # collapsed
    assert notify.toast("different", "body") is True


def test_desktop_channel_switch_gates_everything(realm, monkeypatch):
    """The App-settings channel switch is per machine and outranks the realm's grid."""
    sent = []
    monkeypatch.setattr(notify, "_send", lambda *a: sent.append(a))
    monkeypatch.setattr(notify.os, "name", "nt")
    monkeypatch.setattr(notify, "channel_enabled", lambda c: c != "desktop")
    assert notify.toast("t", "b", realm_root=realm(), event="job_finished") is False
    assert sent == []


def test_channel_switches_default_sensibly(monkeypatch):
    from armada import appconfig
    monkeypatch.setattr(appconfig, "get", lambda k, d=None: d)   # empty config
    assert notify.channel_enabled("inapp") is True
    assert notify.channel_enabled("desktop") is True
    assert notify.channel_enabled("telegram") is False    # needs credentials before it can do anything


def test_unreadable_appconfig_leaves_channels_at_their_defaults(monkeypatch):
    from armada import appconfig

    def boom(*a, **k):
        raise OSError("disk gone")
    monkeypatch.setattr(appconfig, "get", boom)
    assert notify.channel_enabled("desktop") is True
    assert notify.channel_enabled("telegram") is False


def test_both_switches_must_agree(realm, monkeypatch):
    """A channel off on this machine beats the realm wanting it; a realm row off beats the channel
    being on. Either one is enough to stay quiet."""
    monkeypatch.setattr(notify, "channel_enabled", lambda c: True)
    r = realm({"matrix": {"job_failed": {"inapp": True, "desktop": False, "telegram": False}}})
    assert notify.wants(r, "job_failed", "inapp") is True
    assert notify.wants(r, "job_failed", "desktop") is False
    monkeypatch.setattr(notify, "channel_enabled", lambda c: c != "inapp")
    assert notify.wants(r, "job_failed", "inapp") is False


def test_settings_renders_a_cell_for_every_event_and_channel(realm, monkeypatch):
    """The grid must be complete: a missing cell is a preference the owner can't express, and it
    silently reads as 'off'."""
    from armada.webui import pages
    import re as _re
    src = Path(pages.__file__).read_text(encoding="utf-8")
    block = src[src.index("# --- Notifications: an event"):src.index("# --- Realm settings tab ---")]
    assert 'data-ev="{ev}"' in block and 'data-ch="{cid}"' in block
    assert "_notify.EVENTS.items()" in block and "_chans" in block
    # both groups are rendered, so no event can be defined and then never shown
    assert "_notify.AGENTS" in block and "_notify.SYSTEM" in block
    # one test button per channel — a single button could only answer "does it reach me?" for one
    assert "mcNotifTest(this," in block and "for cid, clab in _chans" in block


def test_settings_js_sends_the_whole_grid():
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js"
          / "settings.js").read_text(encoding="utf-8")
    assert "mcNotifPayload" in js and "{matrix:m}" in js
    assert "dataset.ch" in js and "mcNotifCol" in js


def test_providers_are_a_multi_select_ready_for_more_engines():
    """Stored as a list from the start, so adding Codex is a list entry rather than a reshape of
    the setting (and of everyone's saved realm.json)."""
    from armada.webui import pages
    src = Path(pages.__file__).read_text(encoding="utf-8")
    assert '_ENGINES = [' in src and '"codex"' in src
    assert 'class="st-prov"' in src
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js"
          / "settings.js").read_text(encoding="utf-8")
    assert ".st-prov:checked" in js and "providers:provs" in js


def test_saving_providers_keeps_at_least_one(tmp_path):
    """A realm with no engine can't run anything — that's a broken state, not a preference."""
    import inspect
    from armada import serve
    src = inspect.getsource(serve.Handler._save_realm_settings)
    assert 'if provs:' in src, "an empty provider list must be ignored, not saved"


def test_app_settings_offers_all_three_channels():
    from armada.webui import pages
    src = Path(pages.__file__).read_text(encoding="utf-8")
    for c in ("st-ch-inapp", "st-ch-desktop", "st-ch-telegram"):
        assert c in src, f"App settings is missing the {c} channel switch"


def test_non_windows_is_a_silent_no_op(monkeypatch):
    monkeypatch.setattr(notify.os, "name", "posix")
    assert notify.toast("t", "b") is False


def test_a_broken_sender_never_reaches_the_caller(monkeypatch):
    """Notifying must not be able to break the run that triggered it."""
    def boom(*a):
        raise RuntimeError("powershell exploded")
    monkeypatch.setattr(notify, "_send", boom)
    monkeypatch.setattr(notify.os, "name", "nt")
    notify.toast("t", "b")          # dispatched on a daemon thread — must not raise here
    import time
    time.sleep(0.2)                 # let the thread die on its own


def test_runner_notify_helper_swallows_everything(monkeypatch):
    from armada import runner
    monkeypatch.setattr(notify, "toast", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    runner._notify("/nope", "job_started", "t", "b")    # must not raise
