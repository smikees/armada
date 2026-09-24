# `armada/workspace.py`

The realm's workspace root, and the ``{workspace}`` token that makes a realm portable.

A realm is a team, its memory and its jobs — none of which are tied to a machine. What ties them
is the *text* of the jobs: prompts say things like ``D:\Work\Development\feeds.stamih.com``, and
on another computer that folder is somewhere else or spelled differently. In the live realm 191 of
193 absolute references sat in job prompts, and every one of them hung off a single root. That is
the whole problem: one variable, written out 193 times.

So the root becomes a setting (``workspace`` in realm.json) and prompts refer to ``{workspace}``,
which is expanded when a job runs. Move the realm, set the root once, and every job resolves.

Deliberately narrow:

* **One token.** Not a template language. ``{workspace}`` and nothing else, because every extra
  token is another thing that can be wrong in a prompt nobody reads until it fails at 03:00.
* **Expanded at run time, never written back.** The stored prompt keeps the token, so the realm
  stays portable no matter how many times it runs.
* **Unset means unchanged.** A realm with no workspace configured passes text through untouched —
  an old realm keeps working exactly as it did, and the token is opt-in.

### `_realm_json(realm_root)`

—

### `root(realm_root)`

The realm's workspace root, or '' when it has none.

### `configured(realm_root)`

—

### `exists(realm_root)`

Is the configured root actually present on this machine? False when unconfigured.

### `expand(text: str, realm_root)`

Replace {workspace} with this machine's root.

### `has_token(text: str)`

—

### `tokenize(text: str, old_root: str)`

Rewrite literal references to `old_root` as {workspace}. Returns (text, replacements).

### `detect_root(realm_root)`

Guess the workspace root of a realm that predates this setting.

### `migrate(realm_root, old_root: str, *, apply: bool=False)`

Rewrite literal `old_root` references in the realm's job prompts as {workspace}.

### `set_root(realm_root, new_root: str)`

Point the realm at a workspace root on this machine.
