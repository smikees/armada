"""Owner-facing tool permissions and write scope; render from local state only."""
from ._base import E
from .. import access_policy, assets, capabilities, tool_admission


def panel(root, agent, provider):
    try:
        policy = access_policy.load(root, agent)
        data = capabilities._policy_json(root / 'agents' / agent / 'agent.json')
        realm = capabilities._policy_json(root / 'realm.json')
        grants = capabilities.execution_policy(root, agent)
        effective = {row['id']: row for row in tool_admission.describe_access(root, provider, policy, grants)}
    except (OSError, ValueError) as exc:
        return f'<section role="alert"><h3>Access policy needs repair</h3><p>{E(str(exc))}</p></section>'
    rows = []
    edits = []
    defaults = []
    for kind, cap in capabilities.catalogue_flat(root):
        cid = cap.get('id')
        if kind not in capabilities.MCP_KINDS or not cid:
            continue
        rule = policy.rule(cid)
        try:
            names = tool_admission.known_names(root, cap, provider)
        except ValueError as exc:
            return f'<section role="alert"><h3>Tool inventory needs repair</h3><p>{E(str(exc))}</p></section>'
        result = effective[cid]
        permitted = result['can_call']
        denied = result['cannot_call']
        permitted_text = ', '.join(permitted) if permitted else ('No tools granted' if names or cid not in grants.allowed_mcp_ids else
                         'No tool names recorded yet. Refresh tools to see the list.')
        rows.append(f'<details><summary>{E(cap.get("name") or cid)}</summary>'
                    f'<p><b>Can call:</b> {E(permitted_text)}</p>'
                    f'<p><b>Cannot call:</b> {E(", ".join(denied) or "None of the recorded tools")}</p>'
                    + (f'<p>{E(result["reason"])}</p>' if result['reason'] else '') +
                    (f'<p>Explicit names not yet recorded: {E(", ".join(result["literal_names"]))}</p>' if result['literal_names'] else '') +
                    '<p>New tools stay unavailable under a tool policy until the inventory is refreshed.</p>'
                    f'<details data-inventory-connector="{E(cid)}"><summary>Record tool names (owner only)</summary>'
                    '<p>Use the exact names from this connector’s tool list, one per line. '
                    'This also works when an engine cannot refresh names automatically. The access rules still filter every name.</p>'
                    f'<textarea class="mc-field" aria-label="Known connector tool names" data-tool-names>{E(chr(10).join(names))}</textarea>'
                    '<button type="button" class="btn btn-secondary btn-sm" data-save-tool-names>Save tool names</button></details></details>')
        configured = cid in data.get('tool_policy', {})
        edits.append(f'<fieldset data-tool-connector="{E(cid)}"><legend>{E(cap.get("name") or cid)}</legend>'
                     f'<label><input type="checkbox" data-limit-tools {"checked" if configured else ""}> Limit this connector’s tools</label>'
                     f'<label>Allow these names or patterns<textarea class="mc-field" data-allow>{E(chr(10).join(rule.allow or ()))}</textarea></label>'
                     f'<label>Always deny these names or patterns<textarea class="mc-field" data-deny>{E(chr(10).join(rule.deny))}</textarea></label>'
                     '</fieldset>')
        defaults.append(f'<label>{E(cap.get("name") or cid)}: deny by default'
                        f'<textarea class="mc-field" data-default-connector="{E(cid)}">{E(chr(10).join(rule.default_deny))}</textarea></label>')
    writes = ('Builder: realm file restrictions do not apply.' if policy.builder else
              'May write only: ' + (', '.join(policy.write_scope) or 'nowhere') if policy.write_scope is not None else
              'No per-agent write scope is set.')
    readonly = ', '.join(policy.read_only) or 'No realm read-only paths are set.'
    return (f'<section class="mc-access-policy" data-agent="{E(agent)}" data-provider="{E(provider)}" style="margin:20px 0">'
            '<h3>Tools and file access</h3>' + ''.join(rows) +
            f'<p><b>File writes:</b> {E(writes)}</p><p><b>Read-only paths:</b> {E(readonly)}</p>'
            + ('<p>Shell commands and native file writes are disabled. Use the guarded file tool. Reads remain available.</p>' if policy.scoped else '') +
            ('<p>Folder grants cannot change live jobs, approvals, run history, conversations or agent profiles. '
             'Own notes and valid pending job proposals remain subject to their separate checks.</p>' if policy.scoped else '') +
            '<button type="button" class="btn btn-secondary btn-sm" data-refresh-tools>Refresh tool names</button>'
            '<details><summary>Edit access (owner only)</summary><p>One name or glob per line. '
            'An empty enabled allow list allows no tools. Deny always wins. An explicit agent allow overrides a realm default denial. '
            'Connector access must also be granted. Changes are logged and apply to new runs.</p>' + ''.join(edits) +
            f'<label><input type="checkbox" data-limit-writes {"checked" if policy.write_scope is not None else ""}> Limit file writes to these realm folders</label>'
            f'<textarea class="mc-field" aria-label="Allowed write paths" data-write-scope placeholder="Finance/data/**">{E(chr(10).join(policy.write_scope or ()))}</textarea>'
            '<div class="mc-policy-actions"><button type="button" class="btn btn-secondary btn-sm" data-preview-policy="agent">Preview agent access</button>'
            '<button type="button" class="btn btn-primary btn-sm" data-save-agent-policy>Save agent access</button></div>'
            '<details><summary>Realm defaults (all agents)</summary><p>Read-only paths apply to every agent except the builder. '
            'Owner edits through ARMADA remain available.</p>' + ''.join(defaults) +
            f'<label>Read-only paths<textarea class="mc-field" data-read-only>{E(chr(10).join(policy.read_only))}</textarea></label>'
            f'<label>Builder agent ID<input class="mc-field" data-policy-builder value="{E(realm.get("policy_builder", "builder"))}"></label>'
            '<div class="mc-policy-actions"><button type="button" class="btn btn-secondary btn-sm" data-preview-policy="realm">Preview defaults for this agent</button>'
            '<button type="button" class="btn btn-primary btn-sm" data-save-realm-policy>Save realm defaults</button></div></details>'
            f'<p>{len(data.get("_policy_changes", []))} recorded owner changes to this agent’s access.</p></details>'
            '<p role="status" aria-live="polite" data-policy-status></p>'
            '<section data-policy-preview aria-label="Unsaved access preview" hidden></section></section>' + assets.js('accesspolicy'))
