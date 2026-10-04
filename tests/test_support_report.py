"""Reports send their approved content through the relay without a client mail key."""
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


# --- in-app sending through a credential-free relay ---

@pytest.fixture
def post(monkeypatch):
    calls = []
    monkeypatch.setattr(support, "_post", lambda payload: calls.append(payload) or True)
    return calls


def test_send_preserves_the_preview_even_if_logs_change(home, post):
    pv = support.preview("", message="x")
    (util.data_dir() / "logs" / "armada.log").write_text("something new\n", encoding="utf-8")
    assert support.send(pv["token"]) == {"ok": True}
    assert post[0]["text"] == pv["text"]
    assert set(post[0]) == {"id", "subject", "text", "reply_to"}
    assert len(post[0]["id"]) == 32


def test_successful_preview_is_consumed_once(home, post):
    token = support.preview("", message="x")["token"]
    assert support.send(token)["ok"]
    assert "expired" in support.send(token)["error"]
    assert len(post) == 1


def test_uncertain_delivery_saves_content_and_retries_the_same_id(home, monkeypatch):
    calls = []
    def delivery(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise OSError("connection lost")
        return True
    monkeypatch.setattr(support, "_post", delivery)
    token = support.preview("", message="do not lose me")["token"]
    result = support.send(token)
    assert not result["ok"] and "do not lose me" in Path(result["saved"]).read_text(encoding="utf-8")
    assert support.send(token)["ok"]
    assert calls[0] == calls[1]


def test_failed_local_save_still_preserves_retry(home, monkeypatch):
    monkeypatch.setattr(support, "_save_unsent", lambda _: None)
    monkeypatch.setattr(support, "_post", lambda _: False)
    token = support.preview("", message="x")["token"]
    assert support.send(token)["saved"] == ""
    assert token in support._previews


def test_expired_preview_is_not_sent(home, post, monkeypatch):
    token = support.preview("", message="x")["token"]
    monkeypatch.setattr(support.time, "time", lambda: support._previews[token]["at"] + support._PREVIEW_TTL + 1)
    assert support.send(token)["ok"] is False and post == []


def test_relay_request_cannot_carry_a_distributed_mail_key(home, monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setenv("ARMADA_RESEND_KEY", "re_do_not_send_this")
    opener = MagicMock()
    response = opener.open.return_value.__enter__.return_value
    response.status = 200
    response.read.return_value = b'{"ok":true}'
    monkeypatch.setattr(support.urllib.request, "build_opener", lambda *_: opener)
    assert support.send(support.preview("", message="x")["token"])["ok"]
    request = opener.open.call_args.args[0]
    assert request.full_url == "https://armada.stamih.com/api/report.php"
    assert not request.has_header("Authorization")
    assert b"re_do_not_send_this" not in request.data


def test_report_redirects_are_refused():
    import urllib.error
    req = support.urllib.request.Request(support.ENDPOINT)
    with pytest.raises(urllib.error.HTTPError):
        support._NoRedirect().redirect_request(req, None, 307, "redirect", {}, "https://untrusted.example/")


def test_report_size_is_bounded_before_network():
    with pytest.raises(ValueError):
        support._post({"text": "x" * 65537})


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
