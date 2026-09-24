"""The updater (launch plan 5.4, ADR-011): signed releases from GitHub, checked, staged, swapped in.

Everything here runs against a throwaway "install" in tmp_path and a test signing key; the network
is a dict of URL → bytes. The properties that matter are the ones an attacker would test: an
unsigned, re-signed, tampered, replayed-old or oddly-shaped release never reaches the live folder,
and a development checkout never updates itself at all.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from armada import appconfig, ed25519, scheduler, sysjobs, updater, util

SEED = bytes(range(32))
PUB = ed25519.public_key(SEED)
REQ = "pywebview==6.2.1\nbottle==0.13.4\n"
RUNTIME = updater.runtime_tag(REQ, "3.12")


# ---- Ed25519 against RFC 8032 §7.1 ---------------------------------------------------------------

RFC = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
]


@pytest.mark.parametrize("sk,pk,msg,sig", RFC)
def test_ed25519_matches_the_rfc_vectors(sk, pk, msg, sig):
    sk, pk, msg, sig = (bytes.fromhex(x) for x in (sk, pk, msg, sig))
    assert ed25519.public_key(sk) == pk
    assert ed25519.sign(sk, msg) == sig
    assert ed25519.verify(pk, msg, sig)


def test_ed25519_refuses_tampering_malleability_and_junk():
    sk, pk, _, sig = (bytes.fromhex(x) for x in RFC[1])
    msg = b"\x72"
    assert not ed25519.verify(pk, msg + b"!", sig)                  # different message
    assert not ed25519.verify(PUB, msg, sig)                        # different key
    bad = bytearray(sig); bad[0] ^= 1
    assert not ed25519.verify(pk, msg, bytes(bad))                  # damaged R
    s = int.from_bytes(sig[32:], "little") + ed25519.L               # S + L: same point, must be refused
    assert s < 2 ** 256
    assert not ed25519.verify(pk, msg, sig[:32] + s.to_bytes(32, "little"))
    assert not ed25519.verify(pk, msg, sig[:63]) and not ed25519.verify(pk[:31], msg, sig)
    assert not ed25519.verify(b"\xff" * 32, msg, sig)               # not a point


# ---- a fake install -----------------------------------------------------------------------------

@pytest.fixture
def inst(tmp_path, monkeypatch):
    root = tmp_path / "ARMADA"
    pkg = root / "armada"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    (pkg / "support_key.txt").write_text("re_local", encoding="utf-8")
    (root / "installed.json").write_text(json.dumps({"runtime": RUNTIME}), encoding="utf-8")
    for name, val in {"ROOT": root, "PKG": pkg, "MARKER": root / "installed.json",
                      "STAGED": root / "armada.staged", "PREVIOUS": root / "armada.previous",
                      "PUBLIC_KEY": PUB, "__version__": "1.0.0"}.items():
        monkeypatch.setattr(updater, name, val)
    monkeypatch.setattr(updater, "window_open", lambda port=8756: False)
    monkeypatch.setattr(updater, "scheduler_running", lambda: False)
    return root


def _zip(version: str, extra: dict | None = None, init_version: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("armada/__init__.py", f'__version__ = "{init_version or version}"\n')
        zf.writestr("armada/new_module.py", "X = 1\n")
        zf.writestr("armada/__pycache__/junk.pyc", b"\0")
        for k, v in (extra or {}).items():
            zf.writestr(k, v)
    return buf.getvalue()


def _release(version="1.1.0", *, blob=None, runtime=RUNTIME, seed=SEED, manifest_extra=None):
    blob = blob if blob is not None else _zip(version)
    m = {"format": 1, "app": "armada", "version": version, "zip": f"armada-{version}.zip",
         "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "runtime": runtime,
         **(manifest_extra or {})}
    raw = json.dumps(m).encode()
    sig = base64.b64encode(ed25519.sign(seed, raw))
    web = {updater._latest_url(updater.MANIFEST): raw, updater._latest_url(updater.SIGNATURE): sig,
           updater._asset_url(version, f"armada-{version}.zip"): blob}
    asked = []

    def fetch(url, limit):
        asked.append(url)
        if url not in web:
            raise OSError("HTTP Error 404: Not Found")
        return web[url]
    fetch.asked = asked
    fetch.web = web
    return fetch


# ---- check: what gets staged, and what doesn't ---------------------------------------------------

def test_a_signed_newer_release_is_downloaded_checked_and_staged(inst):
    r = updater.check(fetch=_release("1.1.0"))
    assert r["ok"] and r["staged"] == "1.1.0"
    assert updater.staged_version() == "1.1.0"
    assert (inst / "armada.staged" / "new_module.py").exists()
    assert not (inst / "armada.staged" / "__pycache__").exists()
    assert (inst / "armada" / "__init__.py").read_text().count("1.0.0")      # live folder untouched
    assert updater.state()["status"] == "staged"


def test_a_release_signed_by_anyone_else_is_refused(inst):
    r = updater.check(fetch=_release("1.1.0", seed=bytes(32)))
    assert not r["ok"] and "signed" in r["error"]
    assert not updater.staged_version() and not (inst / "armada.staged").exists()


def test_a_tampered_manifest_is_refused(inst):
    f = _release("1.1.0")
    url = updater._latest_url(updater.MANIFEST)
    f.web[url] = f.web[url].replace(b'"1.1.0"', b'"1.1.1"', 1)
    assert not updater.check(fetch=f)["ok"]
    assert not updater.staged_version()


def test_a_zip_that_isnt_the_signed_one_is_refused(inst):
    f = _release("1.1.0")
    f.web[updater._asset_url("1.1.0", "armada-1.1.0.zip")] = _zip("1.1.0", {"armada/evil.py": "x"})
    r = updater.check(fetch=f)
    assert not r["ok"] and "checksum" in r["error"]
    assert not (inst / "armada.staged").exists()


def test_an_old_signed_release_cant_roll_a_copy_back(inst, monkeypatch):
    monkeypatch.setattr(updater, "__version__", "1.2.0")
    f = _release("1.1.0")
    r = updater.check(fetch=f)
    assert r["ok"] and not r["newer"]
    assert not any(u.endswith(".zip") for u in f.asked)


def test_a_release_needing_a_new_runtime_isnt_downloaded(inst):
    f = _release("1.1.0", runtime="py3.13-0000000000000000")
    r = updater.check(fetch=f)
    assert r["needs_installer"] and r["url"] == updater.RELEASES_PAGE
    assert not any(u.endswith(".zip") for u in f.asked) and not updater.staged_version()


@pytest.mark.parametrize("name", ["armada/../evil.py", "evil.py", "/abs/armada/x.py", "C:/armada/x.py"])
def test_zip_entries_outside_the_package_are_refused(inst, name):
    blob = _zip("1.1.0", {name: "boom"})
    r = updater.check(fetch=_release("1.1.0", blob=blob))
    assert not r["ok"] and "layout" in r["error"]
    assert not (inst / "evil.py").exists() and not (inst.parent / "evil.py").exists()


def test_code_that_doesnt_carry_its_signed_version_is_refused(inst):
    blob = _zip("1.1.0", init_version="9.9.9")
    r = updater.check(fetch=_release("1.1.0", blob=blob))
    assert not r["ok"] and not updater.staged_version()


def test_offline_or_no_release_yet_is_a_quiet_error(inst):
    def offline(url, limit):
        raise OSError("HTTP Error 404: Not Found")
    r = updater.check(fetch=offline)
    assert not r["ok"] and r["error"] == "no release published yet"


def test_manifest_shape_is_checked_after_the_signature(inst):
    f = _release("1.1.0", manifest_extra={"zip": "../../armada-1.1.0.zip"})
    r = updater.check(fetch=f)
    assert not r["ok"] and "incomplete" in r["error"]


# ---- a development checkout never updates itself -------------------------------------------------

@pytest.mark.parametrize("why", ["no-marker", "git"])
def test_a_development_checkout_never_updates(inst, why):
    if why == "no-marker":
        (inst / "installed.json").unlink()
    else:
        (inst / ".git").mkdir()
    f = _release("1.1.0")
    r = updater.check(fetch=f)
    assert r["installed"] is False and f.asked == []
    updater.check  # noqa
    assert updater.boot("app") is False and updater.scheduler_pass() is False


def test_this_repo_is_not_an_install():
    assert updater.installed() is False


# ---- applying ------------------------------------------------------------------------------------

def test_apply_swaps_the_folder_and_keeps_the_old_one(inst):
    updater.check(fetch=_release("1.1.0"))
    assert updater.apply_staged() == "1.1.0"
    assert '"1.1.0"' in (inst / "armada" / "__init__.py").read_text()
    assert '"1.0.0"' in (inst / "armada.previous" / "__init__.py").read_text()
    assert (inst / "armada" / "support_key.txt").read_text() == "re_local"      # carried over
    assert not (inst / "armada" / updater._STAGED_INFO).exists()
    assert not (inst / "armada.staged").exists()
    assert updater.state()["applied"] == "1.1.0"


def test_a_failed_swap_leaves_the_live_folder_in_place(inst, monkeypatch):
    updater.check(fetch=_release("1.1.0"))
    real = util._replace_retrying
    calls = []

    def flaky(src, dst, attempts=12):
        calls.append((src, dst))
        if len(calls) == 2:
            raise PermissionError(32, "in use")
        return real(src, dst, attempts=1)
    monkeypatch.setattr(util, "_replace_retrying", flaky)
    assert updater.apply_staged() == ""
    assert '"1.0.0"' in (inst / "armada" / "__init__.py").read_text()
    assert updater.staged_version() == "1.1.0"                                  # still waiting


def test_boot_applies_only_when_no_other_process_runs_the_old_code(inst, monkeypatch):
    updater.check(fetch=_release("1.1.0"))
    monkeypatch.setattr(updater, "scheduler_running", lambda: True)
    assert updater.boot("app") is False
    monkeypatch.setattr(updater, "window_open", lambda port=8756: True)
    assert updater.boot("schedule") is False
    monkeypatch.setattr(updater, "window_open", lambda port=8756: False)
    assert updater.boot("schedule") is True
    assert '"1.1.0"' in (inst / "armada" / "__init__.py").read_text()


def test_the_scheduler_applies_when_quiet_and_restarts(inst, monkeypatch):
    updater.check(fetch=_release("1.1.0"))
    assert updater.scheduler_pass(telegram_busy=True) is False                  # mid-reply: wait
    monkeypatch.setattr(updater, "window_open", lambda port=8756: True)
    assert updater.scheduler_pass() is False                                    # window open: wait
    monkeypatch.setattr(updater, "window_open", lambda port=8756: False)
    appconfig.save({updater.AUTO_KEY: False})
    assert updater.scheduler_pass() is False                                    # automatic off
    appconfig.save({updater.AUTO_KEY: True})
    assert updater.scheduler_pass() is True
    assert '"1.1.0"' in (inst / "armada" / "__init__.py").read_text()


def test_restart_to_update_from_the_window(inst, monkeypatch):
    updater.check(fetch=_release("1.1.0"))
    monkeypatch.setattr(updater, "scheduler_running", lambda: True)
    r = updater.request_apply()
    assert r["waiting"] and updater.apply_requested()
    # the scheduler honours the request even with the window open, then restarts the window
    monkeypatch.setattr(updater, "window_open", lambda port=8756: True)
    restarted = []
    monkeypatch.setattr(updater, "_restart_window", lambda port=8756: restarted.append(1))
    assert updater.scheduler_pass() is True and restarted == [1]
    assert not updater.apply_requested()


def test_restart_to_update_without_a_scheduler_applies_in_the_window(inst):
    updater.check(fetch=_release("1.1.0"))
    r = updater.request_apply()
    assert r["applied"] == "1.1.0"


def test_a_process_left_on_replaced_code_restarts(inst):
    (inst / "armada" / "__init__.py").write_text('__version__ = "1.1.0"\n')
    assert updater.scheduler_pass() is True


def test_the_daemon_releases_its_locks_and_asks_for_a_restart(tmp_path, monkeypatch):
    realm = tmp_path / "realm"
    realm.mkdir()
    (realm / "realm.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(scheduler, "tick", lambda *a, **k: [])
    monkeypatch.setattr(scheduler, "_update_wanted", lambda: True)
    monkeypatch.setattr(scheduler, "_note_running", lambda on: None)
    from armada import telegram
    monkeypatch.setattr(telegram, "start_listener", lambda *a, **k: None)
    assert scheduler.run_daemon(realm, interval=0) == updater.RESTART_RC
    assert scheduler.lock_holder(realm) is None


# ---- bits ----------------------------------------------------------------------------------------

def test_runtime_tag_ignores_comments_blank_lines_and_order():
    a = updater.runtime_tag("# pins\nb==2\n\na==1  # direct\n", "3.12")
    assert a == updater.runtime_tag("a==1\nb==2\n", "3.12")
    assert a != updater.runtime_tag("a==1\nb==3\n", "3.12")
    assert a != updater.runtime_tag("a==1\nb==2\n", "3.13")


def test_the_system_job_switch_is_the_machine_wide_setting(tmp_path):
    assert sysjobs.is_enabled(tmp_path, "app-update") is True
    sysjobs.set_enabled(tmp_path, "app-update", False)
    assert appconfig.get(updater.AUTO_KEY) is False and updater.auto_enabled() is False
    assert sysjobs.is_enabled(tmp_path, "app-update") is False
    assert not (tmp_path / "system_jobs.json").exists()


def test_the_system_job_in_a_development_copy_says_so(tmp_path):
    r = sysjobs._BY_ID["app-update"]["run"](tmp_path)
    assert r["ok"] and "development" in r["detail"]


def test_routes_bar_and_switch_are_wired():
    from armada import serve
    from armada.webui import layout
    assert serve.Handler._GET_EXACT["/api/update-status"] == "_get_update_status"
    assert serve.Handler._POST_JSON["/api/update-auto"] == "_update_auto"
    assert 'id="mc-updbar"' in Path(layout.__file__).read_text(encoding="utf-8")


def test_the_real_public_key_is_a_valid_point():
    assert ed25519._decompress(updater.PUBLIC_KEY) is not None


# ---- the release builder, end to end -------------------------------------------------------------

def test_build_release_output_is_accepted_by_the_updater(tmp_path, inst, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_release", Path(__file__).resolve().parents[1] / "tools" / "build_release.py")
    br = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(br)
    repo = tmp_path / "repo"
    (repo / "armada").mkdir(parents=True)
    (repo / "armada" / "__init__.py").write_text('__version__ = "1.3.0"\n', encoding="utf-8")
    (repo / "armada" / "m.py").write_text("Y = 2\n", encoding="utf-8")
    (repo / "requirements.txt").write_text(REQ, encoding="utf-8")
    g = ["git", "-C", str(repo), "-c", "user.email=t@example.com", "-c", "user.name=t"]
    subprocess.run([*g, "init", "-q"], check=True)
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "commit", "-qm", "r"], check=True)
    (repo / "armada" / "support_key.txt").write_text("local only", encoding="utf-8")   # untracked
    key = tmp_path / "k.key"
    key.write_text("# test\n" + SEED.hex() + "\n", encoding="utf-8")
    monkeypatch.setattr(br, "ROOT", repo)
    out = br.build(key, tmp_path / "dist")
    files = {p.name: p.read_bytes() for p in out.iterdir()}
    with zipfile.ZipFile(io.BytesIO(files["armada-1.3.0.zip"])) as zf:
        assert "armada/support_key.txt" not in zf.namelist()                   # only committed files
    web = {updater._latest_url(updater.MANIFEST): files[updater.MANIFEST],
           updater._latest_url(updater.SIGNATURE): files[updater.SIGNATURE],
           updater._asset_url("1.3.0", "armada-1.3.0.zip"): files["armada-1.3.0.zip"]}
    r = updater.check(fetch=lambda url, limit: web[url])
    assert r["staged"] == "1.3.0"
    assert updater.apply_staged() == "1.3.0"


def test_build_release_refuses_a_key_the_app_doesnt_trust(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_release", Path(__file__).resolve().parents[1] / "tools" / "build_release.py")
    br = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(br)
    key = tmp_path / "k.key"
    key.write_text(bytes(32).hex(), encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "armada").mkdir(parents=True)
    (repo / "armada" / "__init__.py").write_text('__version__ = "1.3.0"\n', encoding="utf-8")
    (repo / "requirements.txt").write_text(REQ, encoding="utf-8")
    g = ["git", "-C", str(repo), "-c", "user.email=t@example.com", "-c", "user.name=t"]
    subprocess.run([*g, "init", "-q"], check=True)
    subprocess.run([*g, "add", "-A"], check=True)
    subprocess.run([*g, "commit", "-qm", "r"], check=True)
    monkeypatch.setattr(br, "ROOT", repo)
    with pytest.raises(SystemExit, match="isn't the one"):
        br.build(key, tmp_path / "dist")
