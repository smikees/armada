"""Talking to your agents from Telegram.

Send `/warren what's our tech concentration?` and it lands in Warren's main thread, runs with his
normal context, autonomy and capabilities, and the answer comes back to the chat. The turn is a
real thread turn, so it's there in the app afterwards too — this is a second door into the same
room, not a side channel.

**Credentials.** ARMADA holds as few as it can get away with, in this order:

1. ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` in the environment.
2. A ``.env``-style file you point ARMADA at. It reads the path, never a copy of the secret — for
   anyone who already has a bot wired into something else, this is the one to use.
3. ARMADA's own store at ``~/.armada/telegram.json``, for someone starting from nothing.

Only (3) means ARMADA is keeping a secret, and it's deliberately outside every realm folder so a
realm export or backup can't carry it off. The file is written 0600 where the OS allows it.

**Set up once.** You paste a bot token, message the bot, and ARMADA learns the chat id itself — no
hunting for a numeric id, and nothing to configure again afterwards. Agent names are registered as
Telegram commands, so they autocomplete in the app.

**Who can talk to it.** Exactly one chat: the one you linked. A Telegram bot is reachable by anyone
who knows its name, and an unlocked bot here would be a stranger driving your agents, so every
message from anywhere else is dropped. Delegated-work limits apply too: a per-hour ceiling, because
each message is an agent run and agent runs cost quota.
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import util
import logging
from .util import swallowed
log = logging.getLogger(__name__)

API = "https://api.telegram.org"
_STORE = "telegram.json"          # in ~/.armada, never in a realm
_STATE = "telegram_state.json"    # per realm: poll offset, who you last addressed, rate counter
_MAX_LEN = 3900                   # Telegram's hard limit is 4096; leave room for the name prefix
_MAX_PER_HOUR = 20                # each message is an agent run, and agent runs spend quota
# What to tell someone who has just asked a question. A real agent turn is a model call with tools,
# so it is tens of seconds, not instant — and the ack only helps if the number is honest.
_ETA = "30–90 seconds"
_HELP = ("Start with a name, then your question:\n"
         "  /warren how exposed are we to tech?\n\n"
         "After that you can just keep typing — a message with no name goes to whoever you asked "
         "last.\n"
         f"Answers take {_ETA}. You'll get a note the moment your message lands.\n\n"
         "/agents — who's here\n/help — this message")


# ---- credentials --------------------------------------------------------------------------------

def _store_path() -> Path:
    from . import util
    return util.data_dir() / _STORE


def _read_store() -> dict:
    try:
        d = json.loads(_store_path().read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa — no store, or an unreadable one, just means "not set up here"
        log.debug('_read_store: failed; returning a fallback', exc_info=True)
        return {}


def _write_store(d: dict) -> None:
    p = _store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    util.write_json_atomic(p, d)
    try:
        os.chmod(p, 0o600)        # best effort: a no-op on Windows, worth having on POSIX
    except OSError:
        pass


def _parse_env_file(path) -> dict:
    """KEY=value pairs out of a .env — quotes stripped, # comments and blanks ignored."""
    out = {}
    try:
        for ln in Path(path).read_text(encoding="utf-8-sig").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:  # noqa — a missing or unreadable file is "no credentials here"
        log.debug('_parse_env_file: failed; ignored', exc_info=True)
    return out


def creds() -> tuple:
    """(token, chat_id, source). Empty strings where nothing is configured."""
    tok = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if tok:
        return tok, chat, "environment"
    st = _read_store()
    envf = str(st.get("env_file") or "").strip()
    if envf:
        d = _parse_env_file(envf)
        t2 = (d.get("TELEGRAM_BOT_TOKEN") or "").strip()
        if t2:
            return t2, (d.get("TELEGRAM_CHAT_ID") or "").strip() or str(st.get("chat_id") or ""), "env file"
    tok = str(st.get("token") or "").strip()
    if tok:
        return tok, str(st.get("chat_id") or "").strip(), "ARMADA"
    return "", "", ""


def configured() -> bool:
    return bool(creds()[0])


def ready() -> bool:
    """Configured *and* pointed at a chat — the point at which it can actually do anything."""
    tok, chat, _src = creds()
    return bool(tok and chat)


def save_token(token: str) -> dict:
    token = str(token or "").strip()
    if not token:
        st = _read_store()
        st.pop("token", None)
        _write_store(st)
        return {"ok": True, "cleared": True}
    if ":" not in token:
        return {"ok": False, "error": "That doesn't look like a bot token (BotFather gives you "
                                      "something like 123456789:AA...)."}
    r = api(token, "getMe")
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error") or "Telegram rejected that token."}
    st = _read_store()
    st["token"] = token
    st["bot"] = (r.get("result") or {}).get("username") or ""
    st.pop("env_file", None)          # an explicit token supersedes a file we were reading
    _write_store(st)
    return {"ok": True, "bot": st["bot"]}


def save_env_file(path: str) -> dict:
    path = str(path or "").strip()
    if not path:
        st = _read_store()
        st.pop("env_file", None)
        _write_store(st)
        return {"ok": True, "cleared": True}
    if not Path(path).is_file():
        return {"ok": False, "error": f"No file at {path}."}
    d = _parse_env_file(path)
    if not (d.get("TELEGRAM_BOT_TOKEN") or "").strip():
        return {"ok": False, "error": "That file has no TELEGRAM_BOT_TOKEN line."}
    st = _read_store()
    st["env_file"] = path
    st.pop("token", None)             # we read the file instead of keeping our own copy
    r = api((d.get("TELEGRAM_BOT_TOKEN") or "").strip(), "getMe")
    st["bot"] = ((r.get("result") or {}) if r.get("ok") else {}).get("username") or ""
    if (d.get("TELEGRAM_CHAT_ID") or "").strip():
        st["chat_id"] = d["TELEGRAM_CHAT_ID"].strip()
    _write_store(st)
    return {"ok": True, "bot": st.get("bot") or "", "chat_id": st.get("chat_id") or ""}


def link_chat() -> dict:
    """Learn the chat id from whatever was last sent to the bot.

    Saves anyone hunting for a numeric chat id: press the button, message the bot, done. It takes
    the most recent update, so if several people have messaged the bot the newest wins — which is
    why the UI tells you to send a message *now*."""
    tok, _chat, _src = creds()
    if not tok:
        return {"ok": False, "error": "Add a bot token first."}
    r = api(tok, "getUpdates", {"limit": 10, "timeout": 0, "allowed_updates": ["message"]})
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error") or "Couldn't reach Telegram."}
    ups = r.get("result") or []
    newest = None
    for u in ups:
        m = u.get("message") or {}
        if (m.get("chat") or {}).get("id"):
            newest = m
    if not newest:
        return {"ok": False, "error": "No message yet. Send your bot any message, then try again."}
    if (newest.get("chat") or {}).get("type") != "private":
        # A group would let every member drive your agents — and agents act with your rights
        # (THREAT_MODEL T8). Link the one-to-one chat with the bot instead.
        return {"ok": False, "error": "That message came from a group. Message the bot directly "
                                      "(a one-to-one chat), then try again."}
    cid = str(newest["chat"]["id"])
    st = _read_store()
    st["chat_id"] = cid
    who = (newest.get("from") or {}).get("username") or (newest.get("from") or {}).get("first_name") or ""
    st["chat_name"] = who
    _write_store(st)
    return {"ok": True, "chat_id": cid, "who": who}


def status() -> dict:
    tok, chat, src = creds()
    st = _read_store()
    return {"configured": bool(tok), "linked": bool(tok and chat), "source": src,
            "bot": st.get("bot") or "", "chat_name": st.get("chat_name") or "",
            "env_file": st.get("env_file") or "", "chat_id": chat}


# ---- the wire -----------------------------------------------------------------------------------

def api(token: str, method: str, payload: dict | None = None, timeout: int = 20) -> dict:
    """One Telegram API call. Never raises: a network blip is data, not a crash."""
    if not token:
        return {"ok": False, "error": "no bot token"}
    url = f"{API}/bot{token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            return {"ok": False, "error": body.get("description") or f"HTTP {e.code}"}
        except Exception:  # noqa
            log.debug('api: failed; error returned to the caller', exc_info=True)
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:  # noqa
        log.debug('api: failed; error returned to the caller', exc_info=True)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _chunks(text: str) -> list:
    """Split on paragraph, then line, then hard — so a long answer arrives whole rather than cut."""
    text = str(text or "").strip() or "(no output)"
    out, cur = [], ""
    for para in text.split("\n\n"):
        if len(para) > _MAX_LEN:
            if cur:
                out.append(cur); cur = ""
            for ln in para.splitlines():
                while len(ln) > _MAX_LEN:
                    out.append(ln[:_MAX_LEN]); ln = ln[_MAX_LEN:]
                if len(cur) + len(ln) + 1 > _MAX_LEN:
                    out.append(cur); cur = ln
                else:
                    cur = (cur + "\n" + ln) if cur else ln
            continue
        if len(cur) + len(para) + 2 > _MAX_LEN:
            out.append(cur); cur = para
        else:
            cur = (cur + "\n\n" + para) if cur else para
    if cur:
        out.append(cur)
    return out or ["(no output)"]


def send(text: str, chat_id: str = "", reply_markup: dict | None = None) -> int:
    """Send text; returns the id of the last message sent, or 0 on failure.

    Plain text, deliberately: agent output is Markdown, and Telegram's parse modes reject anything
    they can't parse — an unbalanced asterisk would drop the whole message."""
    tok, chat, _src = creds()
    chat = str(chat_id or chat)
    if not (tok and chat):
        return 0
    mid = 0
    parts = _chunks(text)
    for i, part in enumerate(parts):
        payload = {"chat_id": chat, "text": part, "disable_web_page_preview": True}
        if reply_markup and i == len(parts) - 1:
            payload["reply_markup"] = reply_markup
        r = api(tok, "sendMessage", payload)
        if not r.get("ok"):
            return 0
        mid = int((r.get("result") or {}).get("message_id") or 0)
    return mid


def ask_for_prompt(agent_disp: str) -> int:
    """Answer a bare /agent by opening a reply box aimed at that agent.

    Telegram's command menu sends the moment you tap it, and there is no way to ask it to fill the
    input box instead — so a tap always arrives here as a command with nothing after it. Rather
    than scolding, this turns that tap into the first half of the exchange: force_reply puts the
    keyboard up with the question already framed, and whatever you type comes back as a reply we
    can route without you typing the name again."""
    return send(f"{agent_disp} is listening — what would you like to ask?",
                reply_markup={"force_reply": True, "selective": False,
                              "input_field_placeholder": f"Ask {agent_disp}…"})


def typing(chat_id: str = "") -> None:
    tok, chat, _src = creds()
    chat = str(chat_id or chat)
    if tok and chat:
        api(tok, "sendChatAction", {"chat_id": chat, "action": "typing"}, timeout=8)


# ---- per-realm state ----------------------------------------------------------------------------

def _state_path(realm_root) -> Path:
    return Path(realm_root) / _STATE


def state(realm_root) -> dict:
    try:
        d = json.loads(_state_path(realm_root).read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa
        log.debug('state: failed; returning a fallback', exc_info=True)
        return {}


def _save_state(realm_root, st: dict) -> None:
    try:
        util.write_json_atomic(_state_path(realm_root), st)
    except Exception:  # noqa
        swallowed(log, '_save_state: failed; ignored')


def _ran_last_hour(st: dict) -> int:
    cut = time.time() - 3600
    return len([t for t in (st.get("runs") or []) if t > cut])


# ---- routing ------------------------------------------------------------------------------------

def _agents(realm_root) -> list:
    """(id, display, is_coordinator) for every agent, read straight off disk."""
    out = []
    d = Path(realm_root) / "agents"
    if not d.is_dir():
        return out
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        try:
            c = json.loads((sub / "agent.json").read_text(encoding="utf-8-sig"))
        except Exception:  # noqa
            swallowed(log, '_agents: failed; skipping this one')
            continue
        out.append((sub.name, c.get("display") or sub.name,
                    bool(c.get("coordinator") or c.get("is_coordinator"))))
    return out


def resolve(realm_root, text: str, last: str = "") -> tuple:
    """(agent_id, prompt, reply) — reply set only when this isn't a prompt at all.

    Accepts /warren, @warren or the display name, and falls back to whoever you addressed last so a
    follow-up doesn't need the name again. With nothing to fall back on it asks rather than guessing:
    sending 'and the other one?' to the wrong agent is worse than one extra round trip."""
    text = str(text or "").strip()
    if not text:
        return "", "", ""
    agents = _agents(realm_root)
    if not agents:
        return "", "", "This realm has no agents yet."
    by_key = {}
    for aid, disp, _c in agents:
        by_key[aid.lower()] = aid
        by_key[disp.lower()] = aid
    head = text.split(None, 1)[0]
    rest = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
    key = head.lstrip("/@").split("@")[0].lower()      # /warren@MyBot → warren, in group chats
    if key in ("help", "start"):
        return "", "", _HELP
    if key in ("agents", "who"):
        lines = [f"/{command_for(aid, disp) or aid} — {disp}" + ("  (coordinator)" if c else "")
                 for aid, disp, c in agents]
        return "", "", "Who's here:\n" + "\n".join(lines)
    if head[:1] in ("/", "@") or key in by_key:
        if key in by_key:
            # An empty prompt is normal, not a mistake: tapping the command menu sends the bare
            # command. dispatch() turns it into a reply box aimed at this agent.
            return by_key[key], rest.strip(), ""
        if head[:1] == "/":
            return "", "", f"No agent called '{key}'. Send /agents to see who's here."
    if last and last in {a for a, _d, _c in agents}:
        return last, text, ""
    coord = next((aid for aid, _d, c in agents if c), "")
    if coord:
        return coord, text, ""
    return "", "", "Start with an agent's name — /agents shows who's here."


def command_for(aid: str, disp: str) -> str:
    """The command to publish for an agent — its NAME where that works, else its folder id.

    You think of the agent as Warren, not as `finance`. Both are accepted when routing, but only
    one can be the thing Telegram autocompletes, and it should be the one you'd have typed. Falls
    back to the id for a name Telegram won't take (spaces, accents, punctuation)."""
    name = str(disp or "").strip().lower()
    if name.isalnum() and name.isascii() and len(name) <= 32:
        return name
    aid = str(aid or "").strip().lower()
    return aid if (aid.isalnum() and aid.isascii() and len(aid) <= 32) else ""


def register_commands(realm_root) -> dict:
    """Publish only /help and /agents.

    Agents deliberately aren't in the menu. Telegram sends a command the moment you tap it and
    offers no way to fill the input box instead, so a menu full of agent names is a menu full of
    ways to send an empty message and then wait for a round trip before you can type the actual
    question. Typing /warren still works — it just isn't offered as a one-tap way to do the wrong
    thing. /agents lists who's here."""
    tok, _chat, _src = creds()
    if not tok:
        return {"ok": False, "error": "not configured"}
    cmds = [{"command": "agents", "description": "Who's here"},
            {"command": "help", "description": "How to use this"}]
    return api(tok, "setMyCommands", {"commands": cmds})


# ---- the pass -----------------------------------------------------------------------------------

def poll(realm_root, wait: int = 0) -> list:
    """New messages from the linked chat since last time. Free: no engine, no quota.

    `wait` is Telegram's long-poll timeout: 0 returns immediately (the fallback job's one-a-minute
    check), anything higher holds the connection open until a message arrives, which is what makes
    an acknowledgement feel instant rather than arriving a minute later."""
    tok, chat, _src = creds()
    if not (tok and chat):
        return []
    st = state(realm_root)
    payload = {"timeout": int(wait), "allowed_updates": ["message"]}
    if st.get("offset"):
        payload["offset"] = int(st["offset"])
    r = api(tok, "getUpdates", payload, timeout=int(wait) + 20)
    if not r.get("ok"):
        return []
    msgs, last_id, ignored = [], st.get("offset") or 0, 0
    for u in (r.get("result") or []):
        last_id = max(last_id, int(u.get("update_id") or 0) + 1)
        m = u.get("message") or {}
        text = (m.get("text") or "").strip()
        if not text:
            continue
        # One chat, and only one. A bot is reachable by anyone who knows its name; without this,
        # a stranger could run your agents and read what comes back.
        if str((m.get("chat") or {}).get("id")) != str(chat) or (m.get("chat") or {}).get("type", "private") != "private":
            ignored += 1
            continue
        msgs.append({"text": text,
                     "reply_to": int(((m.get("reply_to_message") or {}).get("message_id")) or 0)})
    st["offset"] = last_id
    if ignored:
        st["ignored"] = int(st.get("ignored") or 0) + ignored
    _save_state(realm_root, st)
    return msgs


def handle(realm_root, m: dict, engine="claude") -> str:
    """One message, start to finish. Returns 'answered', 'failed', or '' (nothing was run).

    Split out of the polling so the acknowledgement can go out the instant a message arrives —
    which only means anything if something is actually waiting on the wire for it."""
    from . import runner
    st = state(realm_root)
    text, reply_to = m.get("text") or "", int(m.get("reply_to") or 0)
    # Answering the "what would you like to ask?" box: the agent is already decided, so the whole
    # message is the prompt — no name to retype.
    pending = (st.get("awaiting") or {}).get(str(reply_to)) if reply_to else None
    if pending:
        agent_id, prompt, reply = pending, text, ""
    else:
        agent_id, prompt, reply = resolve(realm_root, text, st.get("last_agent") or "")
    if reply:
        send(reply)
        return ""
    if not agent_id:
        return ""
    disp = next((d for a, d, _c in _agents(realm_root) if a == agent_id), agent_id)
    if not prompt.strip():
        mid = ask_for_prompt(disp)
        if mid:
            aw = dict(st.get("awaiting") or {})
            aw[str(mid)] = agent_id
            # Keep the last few: a reply to an older box should still work, but this shouldn't
            # grow without bound.
            st["awaiting"] = dict(list(aw.items())[-20:])
            _save_state(realm_root, st)
        return ""
    if _ran_last_hour(st) >= _MAX_PER_HOUR:
        send("That's the hourly limit for Telegram prompts — each one is a full agent run. "
             "Try again shortly, or use the app.")
        return ""
    # Before the run, not after: a silent minute reads as the message not having arrived.
    send(f"Sent to {disp} — answers usually take {_ETA}.")
    typing()
    st.setdefault("runs", []).append(time.time())
    st["runs"] = [t for t in st["runs"] if t > time.time() - 3600]
    st["last_agent"] = agent_id
    _save_state(realm_root, st)
    try:
        # A real thread turn: same context, autonomy and capabilities as the app, and it's in the
        # thread afterwards. Telegram is a second door into the room, not a side channel.
        res = runner.chat(realm_root, agent_id, "main", prompt, engine=engine, allow_tools=True)
    except Exception as e:  # noqa — one bad turn must not stop the rest
        swallowed(log, 'handle: failed; recorded as an error')
        res = {"ok": False, "output": f"{type(e).__name__}: {e}"}
    out = str(res.get("output") or "").strip()
    if res.get("ok"):
        send(f"{disp}:\n\n{out}")
        return "answered"
    send(f"{disp} couldn't answer that.\n\n{out[:600]}")
    return "failed"


def dispatch(realm_root, engine="claude") -> dict:
    """One non-blocking pass. The fallback path: used by the telegram-inbox system job when no
    listener is running, so Telegram still works (slowly) without the scheduler."""
    if not ready():
        return {"ok": True, "detail": "not connected", "handled": 0}
    msgs = poll(realm_root)
    if not msgs:
        return {"ok": True, "detail": "nothing waiting", "handled": 0}
    handled = failed = 0
    for m in msgs:
        r = handle(realm_root, m, engine)
        handled += r == "answered"
        failed += r == "failed"
    detail = f"{handled} answered" + (f", {failed} failed" if failed else "")
    return {"ok": failed == 0, "detail": detail or "nothing to do", "handled": handled}


# ---- the listener --------------------------------------------------------------------------------

_HEARTBEAT_STALE = 150     # seconds; comfortably longer than one long-poll cycle


def listener_alive(realm_root) -> bool:
    """Is a long-poll listener running somewhere? The fallback job checks this before polling —
    two pollers sharing one getUpdates cursor would race, and each update is delivered once."""
    try:
        return (time.time() - float(state(realm_root).get("listener") or 0)) < _HEARTBEAT_STALE
    except Exception:  # noqa
        log.debug('listener_alive: failed; returning a fallback', exc_info=True)
        return False


_handling = 0          # messages being answered right now, by the listener thread


def busy() -> bool:
    """Is the listener in the middle of answering? The updater (5.4) doesn't restart the scheduler
    then — the reply would be lost with the process."""
    return _handling > 0


def listen(realm_root, engine="claude", stop=None) -> None:
    """Hold a long poll open and answer messages as they land. Runs on a daemon thread.

    The one-a-minute system job was never going to feel responsive: the acknowledgement it sends is
    only as fast as the pass that sends it, so 'message received' could arrive a minute after the
    message. Long-polling costs nothing extra — Telegram holds the connection open rather than us
    asking repeatedly — and turns that minute into about a second."""
    global _handling
    while not (stop is not None and stop.is_set()):
        try:
            if not ready():
                time.sleep(30)
                continue
            st = state(realm_root)
            st["listener"] = time.time()
            _save_state(realm_root, st)
            msgs = poll(realm_root, wait=45)
            if msgs:
                _handling += 1
            try:
                for m in msgs:
                    if stop is not None and stop.is_set():
                        return
                    handle(realm_root, m, engine)
            finally:
                if msgs:
                    _handling -= 1
        except Exception:  # noqa — a listener that dies on one bad message is worse than a slow one
            swallowed(log, 'listen: failed; retrying')
            time.sleep(10)


def start_listener(realm_root, engine="claude"):
    """Start the listener on a daemon thread if Telegram is set up. Returns the thread or None."""
    import threading
    try:
        if not ready():
            return None
        t = threading.Thread(target=listen, args=(realm_root, engine),
                             name="armada-telegram", daemon=True)
        t.start()
        return t
    except Exception:  # noqa
        swallowed(log, 'start_listener: failed; returning a fallback')
        return None
