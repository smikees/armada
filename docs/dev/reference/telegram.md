# `armada/telegram.py`

Talking to your agents from Telegram.

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

### `_store_path()`

—

### `_read_store()`

—

### `_write_store(d: dict)`

—

### `_parse_env_file(path)`

KEY=value pairs out of a .env — quotes stripped, # comments and blanks ignored.

### `creds()`

(token, chat_id, source). Empty strings where nothing is configured.

### `configured()`

—

### `ready()`

Configured *and* pointed at a chat — the point at which it can actually do anything.

### `save_token(token: str)`

—

### `save_env_file(path: str)`

—

### `link_chat()`

Learn the chat id from whatever was last sent to the bot.

### `status()`

—

### `api(token: str, method: str, payload: dict | None=None, timeout: int=20)`

One Telegram API call. Never raises: a network blip is data, not a crash.

### `_chunks(text: str)`

Split on paragraph, then line, then hard — so a long answer arrives whole rather than cut.

### `send(text: str, chat_id: str='', reply_markup: dict | None=None)`

Send text; returns the id of the last message sent, or 0 on failure.

### `ask_for_prompt(agent_disp: str)`

Answer a bare /agent by opening a reply box aimed at that agent.

### `typing(chat_id: str='')`

—

### `_state_path(realm_root)`

—

### `state(realm_root)`

—

### `_save_state(realm_root, st: dict)`

—

### `_ran_last_hour(st: dict)`

—

### `_agents(realm_root)`

(id, display, is_coordinator) for every agent, read straight off disk.

### `resolve(realm_root, text: str, last: str='')`

(agent_id, prompt, reply) — reply set only when this isn't a prompt at all.

### `command_for(aid: str, disp: str)`

The command to publish for an agent — its NAME where that works, else its folder id.

### `register_commands(realm_root)`

Publish only /help and /agents.

### `poll(realm_root, wait: int=0)`

New messages from the linked chat since last time. Free: no engine, no quota.

### `handle(realm_root, m: dict, engine='claude')`

One message, start to finish. Returns 'answered', 'failed', or '' (nothing was run).

### `dispatch(realm_root, engine='claude')`

One non-blocking pass. The fallback path: used by the telegram-inbox system job when no listener is running, so Telegram still works (slowly) without the scheduler.

### `listener_alive(realm_root)`

Is a long-poll listener running somewhere? The fallback job checks this before polling — two pollers sharing one getUpdates cursor would race, and each update is delivered once.

### `busy()`

Is the listener in the middle of answering? The updater (5.4) doesn't restart the scheduler then — the reply would be lost with the process.

### `listen(realm_root, engine='claude', stop=None)`

Hold a long poll open and answer messages as they land. Runs on a daemon thread.

### `start_listener(realm_root, engine='claude')`

Start the listener on a daemon thread if Telegram is set up. Returns the thread or None.
