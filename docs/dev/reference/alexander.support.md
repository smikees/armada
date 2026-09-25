# `armada/alexander/support.py`

Alexander in the app: support conversations (launch plan 6.2, 6.3, 6.6; docs/dev/ALEXANDER.md).

One turn is: assemble what he's allowed to know (the sections PROMPT.md names), run one sealed
engine turn with no tools (Opus 5.5 at High, fixed), then take his reply apart — the prose is
shown, the fenced proposal blocks become cards only if they validate. Nothing he writes acts on its
own; a card acts when the owner presses its button, through the app's own endpoint.

Conversations are this machine's, not a realm's: `~/.armada/alexander/<id>.jsonl`, one line per
message. His tokens are recorded as System usage in the realm he was asked from (sysusage).

### `_dir()`

—

### `new_id()`

—

### `valid_id(cid: str)`

—

### `history(cid: str)`

—

### `_append(cid: str, rec: dict)`

—

### `_now()`

—

### `help_section(question: str, page: str='')`

Every help page — they're small, and a page he can't see is a question he can't answer — with the ones that share the most words with the question and the page first.

### `_json(p: Path)`

—

### `realm_section(realm_root)`

A compact, credential-free picture of the realm: what the owner could see on its pages.

### `logs_section(item: dict | None)`

For a failure: ARMADA's own log lines around it, secrets removed (the 5.6 redactor).

### `page_section(page: str, item: dict | None)`

—

### `build(realm_root, cid: str, message: str, page: str='', item: dict | None=None)`

The user message for one turn: the context sections, the conversation so far, the question.

### `_addon_card(m)`

Validate a proposed add-on exactly as the loader will, in a scratch folder.

### `_report_card(r)`

—

### `parse(text: str, realm_root)`

(the prose, [cards]). At most one card of each kind; anything invalid is dropped silently.

### `ask(realm_root, cid: str, message: str, page: str='', item: dict | None=None, engine=None, on_event=None)`

—

### `install_addon(realm_root, manifest: dict, scope: str='realm')`

Install an add-on he proposed, after validating it again (the card could be stale or edited). Refuses to overwrite an add-on of the same id.
