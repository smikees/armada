# `armada/recommended.py`

ARMADA's recommended capabilities: the curated set the setup wizard offers (launch plan 6.4).

Mihai, 2026-09-25: "a curated selection of capabilities that are most useful and safest relative to
their power that users can enable from the setup phase."

How the list was chosen (reviewed 2026-09-25 against the live sources):

* **Only official sources.** Every entry is in the catalogue the app already mirrors, from
  Anthropic's own `anthropics/skills` repository. Nothing self-published, nothing that needs an
  account, a key or a paid service.
* **Low risk by the app's own rule.** All are skills, which ARMADA files as Low risk: instructions an
  agent reads (catalogue.realm.inspect). Four of them (the document skills) also carry helper
  scripts, which the agent runs with the tools it already has and on files you give it; they add
  no new reach. Said here, and on each entry, because "Low" should never hide that.
* **Useful to anyone.** Things a team running someone's work or life does every week: documents,
  spreadsheets, slides, PDFs, careful writing, a second look at advice.
* **Left out on purpose:** connectors to your accounts (Notion, Slack, GitHub, Google…), browsers
  and terminals, anything with hooks. They can be the most useful of all, and they act in your
  name; each is added from Capabilities, reviewed, one agent at a time.

Each entry names its catalogue key, so the wizard adds it through the normal path
(catalogue.add_to_realm), and the Capabilities page shows it like anything else.

### `for_template(template: str)`

The list with `on` set for this template: an entry's own default, or its default_for.

### `by_key(key: str)`

—
