# `armada/smart_search.py`

Smart search for Add a capability: Alexander searches the sources the owner switched on.

The owner types what they need ("a PDF viewer from ChatGPT", "connectors already in Claude Code").
Alexander gets a sealed turn whose only tools are the read-only searches below; he decides which
sources to ask and with what words, then picks the results most likely to help. Every card on the
page is built from a record a search actually returned (`Session.seen`), never from his prose, so a
capability he imagined cannot appear. Adding anything still goes through the same review as Bring a
link, outside this turn.

Sources are split the way the question is: what you already have (this realm, your skills in other
realms, what Claude Code and ChatGPT already have set up) and where more can be found (directories).

### `_record(source, kind, key, name, description='', *, reach='any', url='', publisher='', have='', action=None, note='')`

—

### `_words(q: str)`

—

### `_score(q_words, *fields)`

—

### `_rank(q, rows, fields, limit)`

—

### `_realm_rows(root)`

—

### `_realm_keys(root)`

—

### `_search_realm(root, q, kind, limit)`

—

### `_catalogue_records(root, source, entries, q, kind, limit, *, action_type='review')`

—

### `_search_my_skills(root, q, kind, limit)`

—

### `_claude_mcp()`

`claude mcp list`, keeping whole names: a plugin's server is "plugin:<plugin>:<server>".

### `_claude_code_rows()`

`claude mcp list` health-checks every server, which is slow: cached for ten minutes.

### `_search_claude_code(root, q, kind, limit)`

—

### `_dir_path()`

—

### `chatgpt_directory(*, refresh=False)`

{'fetched', 'plugins': [...], 'featured': [...]} or {'error'}. Never raises.

### `_search_chatgpt(root, q, kind, limit, *, installed_only=False)`

—

### `_search_engine_connectors(root, q, kind, limit)`

—

### `_search_index(source_ids)`

—

### `_search_registry(root, q, kind, limit)`

—

### `_claude_plugin_source(s)`

—

### `search(root, source: str, query: str='', kind: str='', limit: int=20)`

One source, one query: normalised records. Raises ValueError for an unknown or failed source.

### `_brief(r: dict)`

What Alexander sees of a record: enough to choose, nothing to act on.

### class `Session`

One smart search: the sources it may use, what they returned, and the steps so far.

- `Session.__init__(self, root, sources)` — —
- `Session.step(self, text)` — —
- `Session.list_sources(self)` — —
- `Session.run_search(self, source, query='', kind='', limit=20)` — —

### `_search_tools_class()`

—

### `_extract(text: str)`

—

### `run(root, query: str, sources=None)`

Run one smart search to the end. Returns {ok, summary, results, steps} or {ok: False, error}.

### `_run(sess: Session, query: str)`

—

### `warm()`

Fill the slow lists (Claude Code's health-checked list, ChatGPT's directory) before a search.

### `start(root, query: str, sources=None)`

Start a search in the background; poll status(id).

### `status(jid: str)`

—
