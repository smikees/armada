# `armada/webui/setup_wizard.py`

The setup wizard (launch plan 6.4): ARMADA's first run, with Alexander as the guide.

Replaces the middle of the 5.3 welcome page. Eight steps in two halves (setupflow explains why):

    welcome · checks · folder · team      — before a realm exists (welcome mode, "/")
    capabilities · first job · tour · done — inside the new realm ("/setup")

Both halves are drawn by the same shell, so crossing from one to the other (creating the realm and
switching the server into it) looks like the next step rather than a new page. Everything Alexander
says comes from armada/alexander/wizard_script.py; nothing here is generated.

### `_say(step: str, *keys: str, **vals)`

Alexander's lines for a step, as paragraphs; the first is the lede.

### `_rail(current: str, done_upto: int)`

—

### `_pane(step: str, say: str, body: str, foot: str)`

—

### `_btn(label: str, onclick: str, kind: str='primary', id_: str='', extra: str='')`

—

### `_icons()`

—

### `_shell(panes: str, first: str, data: dict, dark: bool, done_upto: int)`

—

### `_known(realms: list)`

—

### `_q(s: str)`

—

### `_tpl_cards()`

—

### `_presets()`

What the team step shows for each template: names and roles only (the instructions stay on the server — see RealmRoutes._wizard_agents).

### `render_welcome_half(realms: list | None=None, note: str='', dark: bool=False)`

—

### `_cap_rows(template: str)`

—

### `render_realm_half(realm, realm_root, step: str='capabilities', dark: bool=False)`

—
