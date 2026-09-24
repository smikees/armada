"""Make the repo root importable so `from armada import ...` works under pytest — and make sure
running the tests cannot reach the owner.

Telegram credentials deliberately live in ~/.armada, OUTSIDE every realm, so that exporting a realm
can't carry a bot token to another machine. The same property means a test using a throwaway
tmp_path realm still finds the real bot: notify.emit() consults the event grid, where `job_failed`
and `approval_needed` default to telegram=on, and sends for real. Running the suite messaged the
owner's phone once per run — 'Warren: job failed / weekly scan' is a fixture in test_notif_feed.

test_telegram already blocked the network with a fixture of its own. It just wasn't global. It is
now: nothing in the suite touches the network or spawns a desktop toast, and a test that tries
fails loudly rather than quietly buzzing somebody's phone.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _no_outbound(monkeypatch, tmp_path_factory):
    """Cut every outbound channel for the whole suite.

    Autouse and function-scoped, so a test that genuinely exercises a channel can still re-patch
    these: monkeypatch inside the test runs after this fixture, and the later patch wins.
    """
    from armada import notify, telegram

    # The product-level switch, so anything the suite spawns as a subprocess is muted too.
    monkeypatch.setenv(notify.MUTE_ENV, "1")

    # Never read the real credential store, and never see a token from the developer's environment.
    monkeypatch.setattr(telegram, "_store_path",
                        lambda: tmp_path_factory.mktemp("no-tg") / "telegram.json")
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(var, raising=False)

    # Last line of defence. pytest.fail raises a BaseException, so it travels through the
    # `except Exception` guards in the notify path instead of being swallowed into a silent send.
    monkeypatch.setattr(telegram, "api",
                        lambda *a, **k: pytest.fail("a test reached the Telegram network"))
    # Desktop toasts shell out to PowerShell; tests shouldn't spawn processes either.
    monkeypatch.setattr(notify, "_send", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _isolated_machine_config(monkeypatch, tmp_path_factory):
    """Keep the suite out of ~/.armada/config.json.

    That file is machine-level state the app writes as you use it — the app root, the theme, the
    last realm opened. A test exercising any of those wrote the developer's real config: the first
    time a test switched realms it would have moved which realm the app opens on this machine.
    Same reasoning as _no_outbound above — a test run must not change the machine it runs on.
    """
    from armada import appconfig, catalogue
    from armada.catalogue import _shared, sources, realm
    home = tmp_path_factory.mktemp("machine")
    monkeypatch.setattr(appconfig, "_path", lambda: home / "config.json")
    # The catalogue too, and for a second reason: it is not just a file we'd write, it is a file
    # we'd READ. The Capabilities page renders it, so without this the golden page would depend on
    # which plugin marketplaces happen to be installed on the machine running the suite — and
    # would change by itself every time the daily refresh job ran.
    #
    # catalogue.py is now a package (_shared.py / sources.py / realm.py, Phase 2, 2.4/2.9). Each of
    # these names is called bare (not qualified) from more than one of those modules — a `from
    # ._shared import _dir` inside sources.py binds sources.py's OWN copy of the name, so patching
    # only armada.catalogue._dir (the package's re-export) leaves that copy untouched. Every module
    # that resolves the name bare has to be patched, or the code falls through to the real
    # filesystem/network underneath the patch. See catalogue/__init__.py's module docstring.
    monkeypatch.setattr(catalogue, "_dir", lambda: home / "catalogue")
    monkeypatch.setattr(_shared, "_dir", lambda: home / "catalogue")
    monkeypatch.setattr(sources, "_dir", lambda: home / "catalogue")
    monkeypatch.setattr(catalogue, "_marketplaces_dir", lambda: home / "marketplaces")
    monkeypatch.setattr(sources, "_marketplaces_dir", lambda: home / "marketplaces")
    monkeypatch.setattr(realm, "_marketplaces_dir", lambda: home / "marketplaces")
    # "Skills you wrote" walks ~/.claude/skills, ~/.agents/skills and every realm in the machine
    # registry. Unisolated, a test run would list the developer's own skills — and a golden page
    # would change whenever they wrote one.
    monkeypatch.setattr(catalogue, "_skill_roots", lambda: [])
    monkeypatch.setattr(sources, "_skill_roots", lambda: [])
    # And no catalogue HTTP. The daily job now COUNTS the MCP registry — up to 250 paged requests
    # — and any test driving sysjobs.run_due() runs that job. Unstubbed, the suite sat for minutes
    # crawling a live API from inside unit tests. Offline reads as "unreachable", which every
    # caller already handles; a test that wants specific responses re-patches this locally.
    monkeypatch.setattr(catalogue, "_get_json", lambda url: None)
    monkeypatch.setattr(_shared, "_get_json", lambda url: None)
    monkeypatch.setattr(sources, "_get_json", lambda url: None)
    monkeypatch.setattr(realm, "_get_json", lambda url: None)
    # Same for the download side, which fetches skill files from GitHub when one is added.
    monkeypatch.setattr(catalogue, "_get_bytes", lambda url: None)
    monkeypatch.setattr(realm, "_get_bytes", lambda url: None)
    # Registry answers are cached in a module-level dict to keep a filter change off the network.
    # It outlives a test, so one test's stubbed response became the next test's answer. It's a
    # single dict object shared by reference across catalogue/__init__.py, _shared.py and
    # sources.py, so clearing it through any one of those names clears it everywhere.
    catalogue._reg_cache.clear()
    # The updater's machine state (5.4): what it last checked, a pending "restart to update", and the
    # scheduler's pid note. A test must not leave a request on the developer's machine that a real
    # scheduler would act on. And no real release channel: offline reads as "couldn't reach".
    from armada import updater
    monkeypatch.setattr(updater, "_state_path", lambda: home / "update.json")
    monkeypatch.setattr(updater, "_request_path", lambda: home / "update-apply.request")
    monkeypatch.setattr(updater, "_scheduler_pid_path", lambda: home / "scheduler.pid")

    def _no_release_channel(url, limit):
        raise OSError("tests don't reach GitHub")
    monkeypatch.setattr(updater, "_fetch", _no_release_channel)
