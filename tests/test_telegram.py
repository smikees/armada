"""Talking to agents from Telegram.

The two things worth being paranoid about here are that a Telegram bot is reachable by *anyone*
who knows its name, and that every accepted message spends quota on an agent run. Most of these
guard one or the other. The rest cover credential resolution, which has three sources and a
deliberate precedence.
"""
import json
import time

import pytest

from armada import telegram as tg


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    """Never touch the real ~/.armada/telegram.json, and never touch the network."""
    store = tmp_path / "store.json"
    monkeypatch.setattr(tg, "_store_path", lambda: store)
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(tg, "api", lambda *a, **k: pytest.fail("a test hit the network"))
    return store


@pytest.fixture
def realm(tmp_path):
    def _mk(agents=(("hand", "Marcus", True), ("finance", "Warren", False),
                    ("strategy", "Ray", False))):
        for aid, disp, coord in agents:
            d = tmp_path / "agents" / aid
            d.mkdir(parents=True, exist_ok=True)
            (d / "agent.json").write_text(json.dumps({"display": disp, "coordinator": coord}),
                                          encoding="utf-8")
        return tmp_path
    return _mk


# ---- credentials -------------------------------------------------------------------------------

def test_nothing_configured_reads_as_not_configured():
    assert tg.creds() == ("", "", "")
    assert not tg.configured() and not tg.ready()


def test_the_environment_wins(monkeypatch, isolate):
    isolate.write_text(json.dumps({"token": "stored:aa", "chat_id": "1"}), encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env:bb")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "9")
    assert tg.creds() == ("env:bb", "9", "environment")


def test_a_pointed_at_env_file_is_read_not_copied(tmp_path, isolate):
    envf = tmp_path / ".env"
    envf.write_text('TELEGRAM_BOT_TOKEN="111:aaa"\n# comment\nTELEGRAM_CHAT_ID=4242\n', encoding="utf-8")
    isolate.write_text(json.dumps({"env_file": str(envf)}), encoding="utf-8")
    tok, chat, src = tg.creds()
    assert (tok, chat, src) == ("111:aaa", "4242", "env file")
    assert "111:aaa" not in isolate.read_text(encoding="utf-8"), \
        "the whole point of this path is that ARMADA keeps the path, not the secret"


def test_armadas_own_store_is_the_last_resort(isolate):
    isolate.write_text(json.dumps({"token": "222:bbb", "chat_id": "7"}), encoding="utf-8")
    assert tg.creds() == ("222:bbb", "7", "ARMADA")


def test_the_store_lives_outside_every_realm():
    """A realm export zips the realm folder. A credential in there would travel with it."""
    # read the module file, not the function: the fixture has monkeypatched _store_path
    from pathlib import Path
    src = Path(tg.__file__).read_text(encoding="utf-8")
    block = src.split("def _store_path()")[1].split("\ndef ")[0]
    assert "util.data_dir()" in block and "realm" not in block.lower()


def test_a_token_without_a_chat_is_not_ready(isolate):
    isolate.write_text(json.dumps({"token": "222:bbb"}), encoding="utf-8")
    assert tg.configured() and not tg.ready()


def test_an_obvious_non_token_is_rejected_without_calling_telegram():
    r = tg.save_token("hello")
    assert not r["ok"] and "BotFather" in r["error"]


# ---- who is allowed to talk to it ---------------------------------------------------------------

def _updates(*chat_ids):
    return {"ok": True, "result": [
        {"update_id": 100 + i, "message": {"chat": {"id": c}, "text": f"msg{i}"}}
        for i, c in enumerate(chat_ids)]}


def test_only_the_linked_chat_is_heard(realm, isolate, monkeypatch):
    """The one that matters. A bot is reachable by anyone who knows its name; without this, a
    stranger could run the owner's agents and read the answers."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "api", lambda *a, **k: _updates(555, 999, 555))
    assert [m["text"] for m in tg.poll(r)] == ["msg0", "msg2"]
    assert tg.state(r)["ignored"] == 1


def test_the_offset_advances_so_a_message_is_answered_once(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "api", lambda *a, **k: _updates(555, 555))
    tg.poll(r)
    assert tg.state(r)["offset"] == 102
    seen = {}
    monkeypatch.setattr(tg, "api", lambda t, m, p=None, **k: seen.update(p or {}) or {"ok": True, "result": []})
    tg.poll(r)
    assert seen.get("offset") == 102, "the next poll must ask Telegram to forget what we handled"


def test_nothing_is_polled_when_no_chat_is_linked(realm, isolate):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t"}), encoding="utf-8")
    assert tg.poll(r) == []          # the api fixture would fail the test if it were called


# ---- routing -----------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expect", [
    ("/finance how are we?", ("finance", "how are we?")),
    ("@finance how are we?", ("finance", "how are we?")),
    ("Warren how are we?", ("finance", "how are we?")),
    ("/finance@ArmadaBot how are we?", ("finance", "how are we?")),
])
def test_an_agent_can_be_named_several_ways(realm, text, expect):
    aid, prompt, reply = tg.resolve(realm(), text)
    assert (aid, prompt) == expect and not reply


def test_a_follow_up_goes_to_whoever_you_asked_last(realm):
    aid, prompt, reply = tg.resolve(realm(), "and the quarter after?", last="finance")
    assert aid == "finance" and prompt == "and the quarter after?" and not reply


def test_with_no_history_a_bare_message_goes_to_the_coordinator(realm):
    aid, _p, reply = tg.resolve(realm(), "what's up?")
    assert aid == "hand" and not reply


def test_an_unknown_name_asks_rather_than_guessing(realm):
    """Sending 'sell everything' to the wrong agent is worse than one extra round trip."""
    aid, _p, reply = tg.resolve(realm(), "/nobody hello")
    assert not aid and "No agent" in reply


def test_a_bare_command_resolves_to_the_agent_with_no_prompt(realm):
    """Tapping an agent in Telegram's command menu SENDS immediately — there is no way to ask it to
    fill the input box instead — so a bare command is the normal case, not a mistake. dispatch()
    turns it into a reply box aimed at that agent."""
    aid, prompt, reply = tg.resolve(realm(), "/finance")
    assert aid == "finance" and prompt == "" and not reply


def test_help_and_agents_answer_without_running_anything(realm):
    for cmd in ("/help", "/agents", "/start", "/who"):
        aid, _p, reply = tg.resolve(realm(), cmd)
        assert not aid and reply, f"{cmd} should reply directly"
    _a, _p, reply = tg.resolve(realm(), "/agents")
    assert "/warren" in reply and "Warren" in reply


def test_the_published_command_is_the_name_you_would_type():
    """Used by /agents to show the form worth typing — Warren, not `finance` (his folder)."""
    assert tg.command_for("finance", "Warren") == "warren"
    assert tg.command_for("hand", "Marcus") == "marcus"


def test_a_name_telegram_cannot_take_falls_back_to_the_id():
    assert tg.command_for("travel", "Ibn Battuta") == "travel"      # space
    assert tg.command_for("estate", "Palládio") == "estate"         # non-ascii
    assert tg.command_for("x y", "A B") == ""                       # neither works


def test_agents_are_not_in_the_command_menu(realm, isolate, monkeypatch):
    """Telegram sends a command the instant you tap it, so a menu of agent names is a menu of
    one-tap ways to send an empty message and then wait a round trip before typing the question."""
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "1"}), encoding="utf-8")
    sent = {}
    monkeypatch.setattr(tg, "api", lambda t, m, p=None, **k: sent.update(p or {}) or {"ok": True})
    tg.register_commands(realm())
    assert [c["command"] for c in sent["commands"]] == ["agents", "help"]


def test_typing_an_agent_name_still_works(realm):
    """Out of the menu, not out of the product."""
    aid, prompt, _r = tg.resolve(realm(), "/warren how are we?")
    assert (aid, prompt) == ("finance", "how are we?")


# ---- the listener ---------------------------------------------------------------------------------

def test_a_long_poll_asks_telegram_to_hold_the_connection(realm, isolate, monkeypatch):
    """This is what makes the acknowledgement instant: without it the ack is only as fast as the
    once-a-minute pass that sends it, so 'message received' could land a minute after the message."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    seen = {}
    monkeypatch.setattr(tg, "api",
                        lambda t, m, p=None, **k: seen.update(p or {}, _to=k.get("timeout"))
                        or {"ok": True, "result": []})
    tg.poll(r, wait=45)
    assert seen["timeout"] == 45
    assert seen["_to"] > 45, "the HTTP timeout must outlast the long poll or it aborts every cycle"


def test_the_fallback_job_stands_down_while_a_listener_runs(realm, isolate, monkeypatch):
    """Two pollers share one cursor. Telegram hands each update to whoever asks first, so both
    running means they take turns dropping messages."""
    from armada import sysjobs
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    tg._save_state(r, {"listener": time.time()})
    monkeypatch.setattr(tg, "dispatch", lambda *a, **k: pytest.fail("polled behind the listener"))
    out = sysjobs._BY_ID["telegram-inbox"]["run"](r)
    assert out["ok"] and "listener" in out["detail"]


def test_a_stale_heartbeat_hands_the_work_back(realm, isolate, monkeypatch):
    """If the scheduler dies, Telegram should keep working — slowly — rather than silently stop."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    tg._save_state(r, {"listener": time.time() - tg._HEARTBEAT_STALE - 5})
    assert not tg.listener_alive(r)
    from armada import sysjobs
    monkeypatch.setattr(tg, "dispatch", lambda *a, **k: {"ok": True, "detail": "nothing waiting"})
    assert sysjobs._BY_ID["telegram-inbox"]["run"](r)["detail"] == "nothing waiting"


def test_the_listener_is_started_by_the_always_on_process():
    from pathlib import Path
    from armada import scheduler
    src = Path(scheduler.__file__).read_text(encoding="utf-8")
    assert "start_listener" in src, "the scheduler is the process that is always up"


def test_the_listener_survives_a_bad_message(realm, isolate, monkeypatch):
    """A listener that dies on one malformed update is worse than a slow one."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    import threading
    stop = threading.Event()
    calls = []

    def _poll(_r, wait=0):
        calls.append(1)
        if len(calls) >= 3:
            stop.set()
        raise RuntimeError("bad update")
    monkeypatch.setattr(tg, "poll", _poll)
    monkeypatch.setattr(tg.time, "sleep", lambda _s: None)
    tg.listen(r, stop=stop)                 # must return rather than raise
    assert len(calls) >= 3


# ---- cost ----------------------------------------------------------------------------------------

def test_there_is_an_hourly_ceiling_because_each_message_is_a_run(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    st = {"runs": [time.time()] * tg._MAX_PER_HOUR}
    tg._save_state(r, st)
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance hello"}])
    sent = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: sent.append(t) or 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat", lambda *a, **k: pytest.fail("ran an agent past the limit"))
    out = tg.dispatch(r)
    assert out["handled"] == 0
    assert "hourly limit" in sent[0]


def test_an_idle_pass_costs_nothing(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "api", lambda *a, **k: {"ok": True, "result": []})
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat", lambda *a, **k: pytest.fail("woke an agent for nothing"))
    assert tg.dispatch(r)["handled"] == 0


def test_a_reply_becomes_a_real_thread_turn(realm, isolate, monkeypatch):
    """Telegram is a second door into the same room: the turn lands in the agent's main thread, so
    the conversation is there in the app afterwards."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance how exposed are we?"}])
    sent, calls = [], []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: sent.append(t) or 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat",
                        lambda rr, aid, thread, msg, **k: calls.append((aid, thread, msg))
                        or {"ok": True, "output": "About 34%."})
    out = tg.dispatch(r)
    assert out["handled"] == 1
    assert calls == [("finance", "main", "how exposed are we?")]
    assert tg._ETA in sent[0] and "Warren" in sent[0], "an ack goes out before the run, not after"
    assert sent[1].startswith("Warren:") and "About 34%" in sent[1]
    assert tg.state(r)["last_agent"] == "finance"


def test_the_ack_lands_before_the_run_not_after_it(realm, isolate, monkeypatch):
    """A minute of silence reads as nothing having happened. The ack has to be sent before the
    engine call blocks, or it arrives with the answer and tells you nothing."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance hello"}])
    order = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: order.append("send") or 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat",
                        lambda *a, **k: order.append("run") or {"ok": True, "output": "x"})
    tg.dispatch(r)
    assert order == ["send", "run", "send"]


def test_the_ack_says_how_long_it_takes(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance hello"}])
    sent = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: sent.append(t) or 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat", lambda *a, **k: {"ok": True, "output": "x"})
    tg.dispatch(r)
    assert tg._ETA in sent[0]


# ---- the two-step ask ---------------------------------------------------------------------------

def test_a_bare_command_opens_a_reply_box_instead_of_running_anything(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance"}])
    markup = {}
    monkeypatch.setattr(tg, "send",
                        lambda t, chat_id="", reply_markup=None: markup.update(reply_markup or {}) or 77)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat", lambda *a, **k: pytest.fail("ran an agent with no prompt"))
    out = tg.dispatch(r)
    assert out["handled"] == 0
    assert markup.get("force_reply") is True, "the keyboard should open aimed at that agent"
    assert tg.state(r)["awaiting"] == {"77": "finance"}


def test_answering_that_box_needs_no_name(realm, isolate, monkeypatch):
    """The whole point: you tapped Warren, so what you type next is the prompt — not something that
    has to start with his name all over again."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    tg._save_state(r, {"awaiting": {"77": "finance"}})
    monkeypatch.setattr(tg, "poll",
                        lambda _r: [{"text": "how exposed are we?", "reply_to": 77}])
    calls = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat",
                        lambda rr, aid, thread, msg, **k: calls.append((aid, msg))
                        or {"ok": True, "output": "ok"})
    tg.dispatch(r)
    assert calls == [("finance", "how exposed are we?")]


def test_a_reply_to_something_else_routes_normally(realm, isolate, monkeypatch):
    """Replying to an agent's answer shouldn't be mistaken for answering an ask-box."""
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    tg._save_state(r, {"awaiting": {"77": "finance"}, "last_agent": "strategy"})
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "and next quarter?", "reply_to": 999}])
    calls = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat",
                        lambda rr, aid, thread, msg, **k: calls.append((aid, msg))
                        or {"ok": True, "output": "ok"})
    tg.dispatch(r)
    assert calls == [("strategy", "and next quarter?")]


def test_the_awaiting_list_does_not_grow_forever(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    n = [0]

    def _send(t, chat_id="", reply_markup=None):
        n[0] += 1
        return n[0]
    monkeypatch.setattr(tg, "send", _send)
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance"}])
    for _ in range(30):
        tg.dispatch(r)
    assert len(tg.state(r)["awaiting"]) <= 20


def test_a_failed_run_says_so_rather_than_going_quiet(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance hello"}])
    sent = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: sent.append(t) or 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner
    monkeypatch.setattr(runner, "chat", lambda *a, **k: {"ok": False, "output": "engine offline"})
    out = tg.dispatch(r)
    assert not out["ok"] and "couldn't answer" in sent[1] and "engine offline" in sent[1]


def test_one_bad_turn_does_not_stop_the_rest(realm, isolate, monkeypatch):
    r = realm()
    isolate.write_text(json.dumps({"token": "t:t", "chat_id": "555"}), encoding="utf-8")
    monkeypatch.setattr(tg, "poll", lambda _r: [{"text": "/finance a"}, {"text": "/strategy b"}])
    sent = []
    monkeypatch.setattr(tg, "send", lambda t, chat_id="", reply_markup=None: sent.append(t) or 1)
    monkeypatch.setattr(tg, "typing", lambda *a, **k: None)
    import armada.runner as runner

    def _chat(rr, aid, thread, msg, **k):
        if aid == "finance":
            raise RuntimeError("boom")
        return {"ok": True, "output": "fine"}
    monkeypatch.setattr(runner, "chat", _chat)
    tg.dispatch(r)
    answers = [s for s in sent if tg._ETA not in s]        # drop the acks
    assert len(answers) == 2 and answers[1].startswith("Ray:")


# ---- delivery ------------------------------------------------------------------------------------

def test_a_long_answer_is_split_not_truncated():
    body = "\n\n".join("para " + "x" * 500 for _ in range(20))
    parts = tg._chunks(body)
    assert len(parts) > 1
    assert all(len(p) <= tg._MAX_LEN for p in parts)
    assert sum(p.count("para") for p in parts) == 20, "nothing may be dropped"


def test_a_single_enormous_line_is_still_split():
    parts = tg._chunks("y" * (tg._MAX_LEN * 3))
    assert all(len(p) <= tg._MAX_LEN for p in parts)
    assert "".join(parts) == "y" * (tg._MAX_LEN * 3)


def test_messages_go_out_as_plain_text():
    """Agent output is Markdown. Telegram's parse modes reject anything they can't parse, so one
    stray asterisk would drop the whole message."""
    import inspect
    src = inspect.getsource(tg.send)
    assert "parse_mode" not in src


def test_the_notification_channel_is_wired_to_this_module():
    import inspect
    from armada import notify
    src = inspect.getsource(notify._send_telegram)
    assert "telegram" in src and "ready()" in src
    assert "return False" in src, "an unconfigured channel is silent, not an error"


def test_the_status_endpoint_writes_its_own_response():
    """GET handlers write the response; POST handlers return a dict. Returning a dict from a GET
    handler closes the connection with nothing in it — which is what it did."""
    from pathlib import Path
    import armada.routes.settings as _settings_routes  # _telegram_status lives here (Phase 2, 2.3)
    src = Path(_settings_routes.__file__).read_text(encoding="utf-8")
    fn = src.split("def _telegram_status(self")[1].split("\n    def ")[0]
    assert "self._json(" in fn and "\n        return {" not in fn


def test_the_status_endpoint_does_not_echo_the_chat_id():
    from pathlib import Path
    import armada.routes.settings as _settings_routes  # _telegram_status lives here (Phase 2, 2.3)
    src = Path(_settings_routes.__file__).read_text(encoding="utf-8")
    fn = src.split("def _telegram_status(self")[1].split("\n    def ")[0]
    assert 'pop("chat_id"' in fn


def test_the_system_job_declares_itself_as_costing_quota():
    from armada import sysjobs
    j = sysjobs._BY_ID["telegram-inbox"]
    assert j["cost"] == sysjobs.QUOTA, "a message becomes an agent run"
    assert sysjobs.interval_minutes(j) == 1
