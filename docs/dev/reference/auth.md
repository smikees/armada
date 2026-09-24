# `armada/auth.py`

Claude Code sign-in state, and a way to fix it without leaving ARMADA.

When Claude Code's OAuth session lapses, *everything* stops: every agent run fails with
"Failed to authenticate", and usage reporting goes dark. The owner shouldn't have to discover that
from a log and then drop into a terminal — so ARMADA detects the state and can start the official
sign-in for them.

The boundary matters: ARMADA never sees, stores, or transports a credential. `claude auth login`
runs Claude Code's own flow in its own console window; the owner signs in through their browser and
Claude Code writes its own credentials file, exactly as if they'd typed the command themselves.
ARMADA only asks "are you signed in?" afterwards.

`claude auth status --json` is the authoritative answer — better than reading the credentials file,
because it also covers API-key and enterprise auth paths that never touch that file.

### `_launcher()`

—

### `status(force: bool=False)`

{'ok': bool, 'logged_in': bool, 'method': str, 'reason': str}. Never raises.

### `_status_live()`

—

### `start_login(console: bool=True)`

Launch Claude Code's own sign-in. Returns once it's STARTED, not once it's finished — the owner completes it in their browser, then ARMADA re-checks status.
