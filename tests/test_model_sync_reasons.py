"""Why the model-catalogue refresh came back empty — and when that's worth telling anyone.

A notification said "Anthropic's model list wasn't reachable" after a 15ms run: far too fast to
have touched the network. fetch_live() had six ways to return None and reported them all as a
network fault, including the ones where ARMADA had simply declined to ask.
"""
import json

import pytest

from armada import models, sysjobs


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.delenv("ARMADA_NO_MODEL_SYNC", raising=False)
    monkeypatch.setattr(models.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("a test hit the network"))


# ---- the six reasons ---------------------------------------------------------------------------

def test_the_kill_switch_is_reported_as_switched_off(monkeypatch):
    monkeypatch.setenv("ARMADA_NO_MODEL_SYNC", "1")
    assert models.fetch_live_result() == (None, "off")


def test_no_token_is_reported_as_signed_out(monkeypatch):
    monkeypatch.setattr(models.usage_api, "_read_token", lambda: None)
    assert models.fetch_live_result() == (None, "signed-out")


def test_an_expired_token_is_not_a_network_fault(monkeypatch):
    """This is the likely culprit: the sign-in was mid-rotation, so ARMADA never asked. Calling
    that 'wasn't reachable' sends the owner looking at their internet connection."""
    import time
    monkeypatch.setattr(models.usage_api, "_read_token",
                        lambda: ("tok", int(time.time() * 1000)))      # already expired
    assert models.fetch_live_result() == (None, "token-expired")


def test_a_real_network_failure_says_so(monkeypatch):
    import time
    monkeypatch.setattr(models.usage_api, "_read_token",
                        lambda: ("tok", int(time.time() * 1000) + 10 ** 7))

    def _boom(*a, **k):
        raise OSError("no route to host")
    monkeypatch.setattr(models.urllib.request, "urlopen", _boom)
    _m, why = models.fetch_live_result()
    assert why.startswith("unreachable") and "OSError" in why


def test_an_http_error_reports_its_status(monkeypatch):
    import time
    import urllib.error
    monkeypatch.setattr(models.usage_api, "_read_token",
                        lambda: ("tok", int(time.time() * 1000) + 10 ** 7))

    def _401(*a, **k):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    monkeypatch.setattr(models.urllib.request, "urlopen", _401)
    assert models.fetch_live_result()[1] == "http-401"


def test_the_old_signature_still_works(monkeypatch):
    """fetch_live() has other callers; it keeps returning list-or-None."""
    monkeypatch.setenv("ARMADA_NO_MODEL_SYNC", "1")
    assert models.fetch_live() is None


# ---- what the owner is told ----------------------------------------------------------------------

@pytest.mark.parametrize("reason,is_failure,says", [
    ("off", False, "switched off"),
    ("signed-out", False, "sign-in"),
    ("token-expired", False, "refreshing"),
    ("empty-response", True, "empty"),
    ("unexpected-response", True, "unexpected"),
    ("unreachable (OSError)", True, "wasn't reachable"),
    ("http-500", True, "refused"),
])
def test_each_reason_gets_an_honest_sentence(reason, is_failure, says, monkeypatch, tmp_path):
    monkeypatch.setattr(models, "refresh", lambda _r: {"ok": False, "reason": reason})
    out = sysjobs._job_model_catalog(tmp_path)
    assert out["ok"] is not is_failure, f"{reason} should{'' if is_failure else ' not'} be a failure"
    assert says in out["detail"], out["detail"]


def test_a_self_healing_state_is_not_recorded_as_a_failure(monkeypatch, tmp_path):
    """A signed-out session is already shown by the sign-in banner; recording it as a job failure
    puts a red mark on the Jobs page for something that isn't broken."""
    monkeypatch.setattr(models, "refresh", lambda _r: {"ok": False, "reason": "signed-out"})
    assert sysjobs._job_model_catalog(tmp_path)["ok"] is True


# ---- not crying wolf ------------------------------------------------------------------------------

def _always_fails(realm_root):
    return {"ok": False, "detail": "nope"}


def test_a_single_failure_does_not_interrupt(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", _always_fails)
    monkeypatch.setattr("armada.notify.emit", lambda *a, **k: sent.append(a))
    sysjobs.run_one(tmp_path, "prune-history")
    assert sent == [], "one miss of a cached-data refresh is invisible and usually self-healing"


def test_a_pattern_does_interrupt(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", _always_fails)
    monkeypatch.setattr("armada.notify.emit", lambda *a, **k: sent.append(a))
    for _ in range(sysjobs._NOTIFY_AFTER_FAILS):
        sysjobs.run_one(tmp_path, "prune-history")
    assert len(sent) == 1
    assert "3 times in a row" in sent[0][3], "and it should say that it's a pattern"


def test_the_counter_resets_on_success(monkeypatch, tmp_path):
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", _always_fails)
    sysjobs.run_one(tmp_path, "prune-history")
    sysjobs.run_one(tmp_path, "prune-history")
    assert sysjobs.state(tmp_path)["prune-history"]["fails"] == 2
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run",
                        lambda _r: {"ok": True, "detail": "fine"})
    sysjobs.run_one(tmp_path, "prune-history")
    assert sysjobs.state(tmp_path)["prune-history"]["fails"] == 0


def test_the_failure_is_still_recorded_even_when_it_does_not_notify(monkeypatch, tmp_path):
    """Quiet is not the same as hidden — the Jobs page still shows it went wrong."""
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", _always_fails)
    monkeypatch.setattr("armada.notify.emit", lambda *a, **k: None)
    sysjobs.run_one(tmp_path, "prune-history")
    s = sysjobs.state(tmp_path)["prune-history"]
    assert s["status"] == "error" and s["detail"] == "nope"
