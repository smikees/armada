# `armada/setupflow.py`

The setup wizard's server side (launch plan 6.4; the page is webui/setup_wizard.py).

The wizard runs in two halves because a realm doesn't exist until halfway through:

* **Before the realm** (the server's welcome mode, no realm open): welcome, checks, folder, team.
  "Appoint the team" creates the realm and switches the server into it.
* **In the realm** (`/setup`): capabilities, first job, tour, done.

Progress is kept in the realm's own `realm.json` under `setup` — `{"step": …, "started": …}` while
it's under way and `{"done": …}` once finished — so closing the window halfway and opening ARMADA
again lands back on the step you were on, instead of on an Overview with half a setup behind it.
Realms made any other way (the New realm dialog, adopting a folder) never get the key and never see
the wizard.

### `_now()`

—

### `_rj(realm_root)`

—

### `state(realm_root)`

—

### `needs_setup(realm_root)`

True while a wizard-made realm hasn't finished its setup.

### `current_step(realm_root)`

—

### `_update(realm_root, fn)`

—

### `begin(realm_root, owner: str='')`

Mark a freshly made realm as mid-setup, and record the owner's name where the app keeps it (realm.json `user.name`, which Settings → User edits and every agent reads).

### `set_step(realm_root, step: str)`

—

### `finish(realm_root)`

Setup is over: record it, and make sure the scheduler is running (the wizard promised).

### `_entry_for(r: dict)`

A catalogue entry for a recommendation, for when the catalogue hasn't been fetched yet (a brand-new install: the daily refresh hasn't run). Same shape the catalogue writes.

### `add_recommended(realm_root, key: str)`

Add one recommended capability and switch it on for the realm. Only keys on the curated list are accepted: this endpoint exists for the wizard, not as a second way into the catalogue.

### `_enable(realm_root, cid: str)`

—

### `brief_prompt(owner: str='')`

The message the wizard sends to the coordinator on the owner's behalf. Shown to the owner before it's sent, as it will appear in the thread.

### `script()`

Everything the page needs from Alexander's script, as data.

### `recommended_for(template: str)`

—

### `template_of(realm_root)`

—

### `owner_of(realm_root)`

—

### `caps_on(realm_root)`

How many capabilities are switched on in the realm (the done step's summary, after a reload).

### `brief_done(realm_root, agent_id: str)`

Did the first brief happen (its thread has turns)? For the summary after a reload.
