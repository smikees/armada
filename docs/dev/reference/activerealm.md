# `armada/activerealm.py`

Which realm the app opens when nobody says — the last one you were actually in.

Switching realms used to live entirely in the running process: `/switch` moved `Handler.realm`
and that was the end of it. Update & Restart carried the change forward (it re-execs with the
live realm), but a cold start did not — the launcher passed a path chosen when it was written,
so closing the app and reopening it silently put you back in a realm you had left, possibly days
ago, with a full week of someone else's jobs on the dashboard. A switch that survives a restart
but not a relaunch is worse than no memory at all, because the two behave differently and nothing
on screen says which one you just did.

So the active realm is remembered on the machine, beside the app root and the visual theme: it is
a property of this install, not of any realm, and not of the folder the launcher happens to point
at. An explicit path still wins — someone typing `armada app <folder>` means that folder, and it
becomes the remembered one — but with no path given, the app reopens where you left it.

### `is_realm(path)`

Does this folder look like a realm ARMADA can open?

### `remembered()`

The last realm the app was in, or '' when there isn't one that still exists.

### `remember(path)`

Record `path` as the realm the app is in. Best-effort; never raises at the caller.

### `resolve(explicit: str='')`

The realm to open: what was asked for, else where we were, else the one we know about.

### `every()`

Every realm ARMADA knows about, the active one first.

### `_registered()`

Paths from ~/.armada/realms.json that still exist as realms.

### `no_realm_message()`

What to tell someone when there is nothing to open.
