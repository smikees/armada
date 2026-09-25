"""Report an issue (launch plan 5.6). The network is never touched here: support._post is replaced.

What these hold: nothing secret leaves in a report; what's sent is exactly what was shown; nothing
the person wrote is lost when sending fails; the key is never in the repo.
"""
import json
import subprocess
from pathlib import Path

import pytest

from armada import support, util


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    logs = util.data_dir() / "logs"
    logs.mkdir(parents=True)
    (logs / "armada.log").write_text(
        "2026-09-24 10:00 INFO armada.serve: ARMADA serving on :8756 (realm=C:\\Users\\mihai\\Realms\\Home)\n"
        "2026-09-24 10:01 ERROR key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUv leaked, resend re_AbCdEfGhIjKlMnOpQrSt12\n"
        "2026-09-24 10:02 ERROR telegram 123456789:AAHfakefakefakefakefakefakefake1234 failed\n"
        "2026-09-24 10:03 WARNING Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789\n"
        "2026-09-24 10:04 INFO mail from someone@example.com and owner@home.net\n", encoding="utf-8")
    (logs / "scheduler.log").write_text("2026-09-24 09:00 INFO tick\n", encoding="utf-8")
    monkeypatch.setattr(support, "_previews", {})
    return tmp_path


class _Post:
    def __init__(self, status=200, body='{"id":"x"}'):
        self.status, self.body, self.calls = status, body, []

    def __call__(self, payload, key, timeout=20):
        self.calls.append((payload, key))
        return self.status, self.body


@pytest.fixture
def post(monkeypatch):
    p = _Post()
    monkeypatch.setattr(support, "_post", p)
    monkeypatch.setattr(support, "key", lambda: "re_testkey_notreal_0000")
    return p


# --- redaction -----------------------------------------------------------------------------------

def test_secrets_emails_and_the_user_name_are_removed(home):
    text = support.build("", message="it broke")["text"]
    for leak in ("sk-ant-api03", "re_AbCdEf", "AAHfakefake", "abcdefghijklmnopqrstuvwxyz0123456789",
                 "someone@example.com", "owner@home.net", "\\mihai\\"):
        assert leak not in text, leak
    assert "[anthropic-key]" in text and "[telegram-token]" in text and "C:\\Users\\<user>" in text


def test_the_address_the_person_typed_is_kept(home):
    text = support.build("", message="x", email="owner@home.net")["text"]
    assert "Reply to: owner@home.net" in text and "owner@home.net and" not in text.split("Reply to")[0]


def test_logs_are_left_out_when_asked(home):
    text = support.build("", message="x", include_logs=False)["text"]
    assert "armada.log" not in text and "chose not to send them" in text


def test_the_report_carries_what_triage_needs(home):
    r = support.build("", message="The jobs page froze\nafter I clicked Run", page="/jobs", title="ARMADA — Jobs")
    assert r["subject"] == "[ARMADA beta] The jobs page froze"
    for want in ("The jobs page froze", "Page: ARMADA — Jobs — /jobs", "App: ARMADA", "Platform:", "Python:",
                 "last 5 lines of armada.log"):
        assert want in r["text"], want


# --- preview, then send exactly that ----------------------------------------------------------------

def test_send_sends_the_previewed_text_even_if_the_logs_moved_on(home, post):
    pv = support.preview("", message="x")
    (util.data_dir() / "logs" / "armada.log").write_text("something new\n", encoding="utf-8")
    assert support.send(pv["token"]) == {"ok": True}
    payload, _ = post.calls[0]
    assert payload["text"] == pv["text"] and "something new" not in payload["text"]
    assert payload["to"] == ["armada@stamih.com"] and "reports@armada.stamih.com" in payload["from"]


def test_a_token_sends_once(home, post):
    pv = support.preview("", message="x")
    assert support.send(pv["token"])["ok"]
    r = support.send(pv["token"])
    assert r["ok"] is False and "expired" in r["error"] and len(post.calls) == 1


def test_reply_to_only_when_given(home, post):
    support.send(support.preview("", message="x", email="me@home.net")["token"])
    support.send(support.preview("", message="y")["token"])
    assert post.calls[0][0]["reply_to"] == "me@home.net" and "reply_to" not in post.calls[1][0]


def test_a_failed_send_saves_the_report_and_says_where(home, post):
    post.status, post.body = 403, '{"message":"forbidden"}'
    pv = support.preview("", message="please don't lose this")
    r = support.send(pv["token"])
    assert r["ok"] is False and "armada@stamih.com" in r["error"]
    saved = Path(r["saved"])
    assert saved.is_file() and "please don't lose this" in saved.read_text(encoding="utf-8")


def test_no_key_means_saved_not_sent(home, monkeypatch):
    monkeypatch.setattr(support, "key", lambda: "")
    r = support.send(support.preview("", message="x")["token"])
    assert r["ok"] is False and "no sending key" in r["error"] and Path(r["saved"]).is_file()


def test_the_hourly_limit_holds(home, post):
    for _ in range(support.PER_HOUR):
        assert support.send(support.preview("", message="x")["token"])["ok"]
    r = support.send(support.preview("", message="x")["token"])
    assert r["ok"] is False and len(post.calls) == support.PER_HOUR and Path(r["saved"]).is_file()


# --- the key never enters the repo -------------------------------------------------------------------

def test_the_key_file_is_ignored_and_untracked():
    root = Path(support.__file__).resolve().parents[1]
    assert "armada/support_key.txt" in (root / ".gitignore").read_text(encoding="utf-8")
    tracked = subprocess.run(["git", "ls-files", "armada/support_key.txt"], cwd=root,
                             capture_output=True, text=True).stdout.strip()
    assert tracked == ""


def test_key_accepts_only_a_resend_key(monkeypatch, tmp_path):
    monkeypatch.setattr(support, "KEY_FILE", tmp_path / "k.txt")
    monkeypatch.delenv("ARMADA_RESEND_KEY", raising=False)
    assert support.key() == ""
    (tmp_path / "k.txt").write_text("not-a-key\n", encoding="utf-8")
    assert support.key() == ""
    (tmp_path / "k.txt").write_text("re_abc123\n", encoding="utf-8")
    assert support.key() == "re_abc123"


# --- wiring ------------------------------------------------------------------------------------------

def test_reporting_is_reached_through_alexander_beside_the_gear():
    """Since 6.2 the icon beside the gear is Alexander; Report an issue is in his drawer, and his
    report card opens the same dialog pre-filled."""
    from armada import serve
    from armada.webui import layout
    src = Path(layout.__file__).read_text(encoding="utf-8")
    assert 'onclick="mcAlexOpen()"' in src and "_SUPPORT_JS" in src and "_ALEXANDER_JS" in src
    js = (Path(layout.__file__).parent / "static" / "js" / "alexander.js").read_text(encoding="utf-8")
    assert "mcSupportOpen()" in js and "mcSupportOpen({message:c.message})" in js
    assert serve.Handler._POST_JSON["/api/support-preview"] == "_support_preview"
    assert serve.Handler._POST_JSON["/api/support-send"] == "_support_send"


def test_a_report_needs_words():
    from armada.routes.settings import SettingsRoutes
    class H(SettingsRoutes):
        realm = ""
    assert H()._support_preview({"message": "  "})["ok"] is False
