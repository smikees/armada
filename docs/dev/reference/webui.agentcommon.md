# `armada/webui/agentcommon.py`

Shared agent/realm page helpers (Phase 3 split of agentpages): job cards, artefact gathering, autonomy/colour controls, filter dropdowns and the status-filter palette.

### `_realm_cfg_value(realm_root, key: str, fallback: str='')`

—

### `_inherit_label(current: str)`

'inherit realm default (high)' rather than a bare 'inherit'.

### `_effort_options(realm_root, selected: str='', inherit: bool=False)`

<option>s for an effort <select>. `inherit` adds the leading blank option, labelled with the realm's own default so every inherit dropdown on the page reads the same way.

### `_model_options(realm_root, selected: str='', inherit: bool=False)`

<option>s for a model <select>, driven by the synced catalog (value=id, text=display name, newest-first). Preserves a stored value no longer offered (e.g. a retired model) so an agent or realm keeps its pick; `inherit` adds the leading 'inherit (realm default)' blank option.

### `_agent_color_control(current: str, field_id: str)`

Preset swatches (the graph palette) + a custom colour picker, writing to a hidden field.

### `_job_proposals_block(realm, realm_root, only_agent: str='')`

A highlighted 'Proposed jobs' panel listing agent-authored proposals awaiting approval. Used on both the realm Jobs section (all agents) and an agent's own Jobs tab (only_agent).

### `_autonomy_control(current: str, field_id: str)`

—

### `_gather_artifacts(realm, realm_root, only_agent: str=None)`

Every artifact across the realm: input artifacts (owner attachments on user turns) and output artifacts (files agents wrote, on assistant turns). One row per artifact, with its thread owner, thread, type, extension, path, and last-touched date (the file's mtime if it's on disk, else the turn timestamp). Sorted newest-touched first.

### `_art_meta(name: str, agent, thread_title: str, thread_slug: str, kind: str, path: str, ts: str)`

—

### `_realm_artefacts(realm, realm_root, only_agent: str=None)`

—
