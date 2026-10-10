# `armada/connector_registry.py`

Logical connectors with explicit provider-local registrations; no credential copying.

### `endpoint(value)`

Only shareable HTTPS endpoints belong in a portable realm, never URL credentials.

### `valid_name(value, provider)`

—

### `_public_endpoint(value)`

Imported private proxy paths can embed credentials; retain only known public routes.

### `binding(cap, provider)`

—

### `provider_cap(cap, provider)`

Runtime facade; preserve the logical capability identity in grants/UI.

### `policy_bindings(cap)`

—

### `inventory(provider, realm_root=None)`

Names and safe remote URLs only. Headers, env, OAuth and local commands stay private.

### `verify_registrations(requirements, registrations)`

A linked name cannot silently start pointing an agent at another service.

### `_row_service(cap: dict)`

The curated service a realm row stands for, if any ('' when it is something else).

### `added_for(realm_root)`

{service id: set of engines it is already added for} — 'any' for an open server.

### `catalogue_entries()`

The curated services as Add a capability results, beside the mirrored sources.

### `save(realm_root, *, name='', url='', provider='', server_name='', capability='', service='', account_label='', engine='')`

Add a remote connector or explicitly link one existing engine registration.

### `add_codex_plugin(realm_root, plugin, *, name='', description='')`

Add a ChatGPT plugin from the directory as its own Codex-only connector row.

### `unlink(realm_root, capability, provider)`

Remove this realm's binding only; never revoke shared provider credentials.

### `model_change_warning(realm_root, agent, before, after)`

Explain a provider switch before saving; runtime preflight remains authoritative.
