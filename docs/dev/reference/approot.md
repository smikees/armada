# `armada/approot.py`

The app root — the one folder on this machine that ARMADA is allowed to work in.

Set once, when ARMADA is first set up. Every realm lives inside it, and nothing an agent does is
supposed to reach outside it. One folder to point at, one folder to back up, one folder to reason
about when asking "what can this thing actually touch".

Why a machine-level setting rather than a per-realm one: containment you can turn off per realm is
not containment. The root is the boundary for the install; a realm chooses where *inside* it to
live, not whether to be inside it.

This module owns two things: what the root is, and whether a given path is inside it. It does not
enforce anything at run time — see `armada.permissions` for what the engine is actually told, and
be careful to keep the difference clear in your head. A path check here is ARMADA refusing to set
something up; it is not a guarantee about what a running agent can reach.

### `root()`

The configured app root, or '' when ARMADA hasn't been set up yet.

### `configured()`

—

### `exists()`

—

### `set_root(path: str)`

Point ARMADA at its root folder. Refuses a path that isn't a folder on this machine.

### `contains(path)`

Is `path` inside the app root? False when no root is set — nothing is 'inside' nothing.

### `check(path)`

Would ARMADA accept a realm at `path`? Returns {ok, error} with a sentence a person can act on.

### `suggest_for(path)`

If someone points at a folder outside the root, what would we move it to?
