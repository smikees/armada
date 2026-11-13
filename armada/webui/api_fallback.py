"""Compact engine/agent entry points and the shared owner API setup dialog."""
from .. import api_fallback
from ..assets import js
from ..icons import _icon
from ._base import E


def setup(provider='claude', root=None, agent=''):
    if provider not in api_fallback.SUPPORTED:
        return ''
    state = api_fallback.settings(provider, root, agent)
    suffix = provider+('-'+agent if agent else '')
    ident = 'mc-api-fallback-'+suffix
    title = 'Claude API usage fallback'
    if agent:
        from pathlib import Path
        from .. import util
        profile = util.read_json_state(Path(root)/'agents'/agent/'agent.json', default=dict)
        title = 'Claude API fallback — '+str(profile.get('display') or profile.get('name') or agent)
    label = 'Manage API usage fallback' if state['managed'] else 'Set up API usage fallback'
    status = ('Critical jobs only' if state['ready'] else 'Off' if state['managed'] else 'Not set up')
    if agent:
        options = [('engine', 'Use the Claude engine key'), ('agent', 'Use a separate key for this agent'), ('off', 'No API fallback for this agent')]
        controls = (f'<label class="mc-label" for="{ident}-source">API key for this agent</label>'
                    f'<select class="mc-field" id="{ident}-source" data-fallback-source onchange="mcFallbackSource(this)">'
                    + ''.join(f'<option value="{value}"{" selected" if value == state["key_source"] else ""}>{text}</option>' for value, text in options)+'</select>'
                    '<p class="mc-hint">For a separate agent budget, create a Console workspace, set its spend limit, and use a key scoped to that workspace. A shared key shares its budget.</p>')
    else:
        controls = (f'<label class="mc-fallback-enable"><input type="checkbox" data-fallback-enabled'
                    + (' checked' if state['enabled'] or not state['managed'] else '')
                    + '> Enable fallback for critical jobs</label>')
    saved = state['key_saved'] if agent and state['key_source'] == 'agent' else state['engine_key_saved']
    key_area = (f'<div data-fallback-key-area{(" hidden" if agent and state["key_source"] != "agent" else "")}>'
                f'<label class="mc-label" for="{ident}-key">Anthropic API key</label>'
                f'<input class="mc-field" id="{ident}-key" type="password" autocomplete="new-password" data-fallback-key '
                'placeholder="Paste your workspace API key">'
                '<p class="mc-hint" data-fallback-key-status>'+('A key is saved. Leave this empty to keep it.' if saved else 'No key saved for this selection.')+'</p>'
                '<label data-fallback-remove-row'+('' if saved else ' hidden')+'><input type="checkbox" data-fallback-remove> Remove the saved key</label></div>')
    return (f'<div class="mc-fallback-entry" data-fallback-entry="{E(suffix)}">'
            f'<button type="button" class="btn btn-secondary" data-fallback-open="{ident}" onclick="mcOpenApiFallback(\'{ident}\')">{label}</button>'
            f'<span class="mc-hint" data-fallback-summary>{status}</span></div>'
            f'<div id="{ident}" class="mc-modal-ov" data-api-fallback data-provider="{provider}" data-agent="{E(agent)}" hidden '
            'onclick="if(event.target===this)mcCloseApiFallback(this)">'
            f'<div class="mc-modal-box mc-api-fallback-dialog" role="dialog" aria-modal="true" aria-labelledby="{ident}-title">'
            f'<div class="mc-api-fallback-heading"><h3 id="{ident}-title">{E(title)}</h3>'
            f'<button type="button" class="btn btn-ghost" data-fallback-dismiss aria-label="Close API fallback setup" onclick="mcCloseApiFallback(this)">{_icon("x",18)}</button></div>'
            '<p>Use your subscription first. Approved critical jobs switch to API credit when a session or weekly limit is reached.</p>'
            '<ol class="mc-fallback-steps">'
            '<li><a href="https://platform.claude.com/settings/billing" target="_blank" rel="noopener noreferrer">Check API credit</a> in the Console organization linked to your Claude plan. Keep auto-reload off if you only want to use existing credit.</li>'
            '<li><a href="https://platform.claude.com/settings/spend-limits" target="_blank" rel="noopener noreferrer">Set a spending limit</a> in Claude Console. Anthropic enforces it, including calls made outside Armada.</li>'
            '<li><a href="https://platform.claude.com/settings/keys" target="_blank" rel="noopener noreferrer">Create a workspace API key</a> and paste it below.</li></ol>'
            + controls+key_area+
            '<p class="mc-hint">Claude Console manages your budget and available credit. Armada reports costs for its own runs only.</p>'
            '<details><summary>Storage and connector details</summary>'
            '<p class="mc-hint">Keys are saved on this computer outside realm exports. Armada cannot read your Console spending cap from this key.</p>'
            '<p class="mc-hint">Jobs that need a subscription-only connector keep their configured wait-or-fail behavior. Fallback never silently removes a required connector or repeats an unsafe tool action.</p></details>'
            '<p role="status" aria-live="polite" data-fallback-feedback></p>'
            '<div class="mc-api-fallback-actions"><button type="button" class="btn btn-secondary" data-fallback-test onclick="mcTestApiFallback(this)">Test key</button>'
            '<button type="button" class="btn btn-secondary" data-fallback-dismiss onclick="mcCloseApiFallback(this)">Cancel</button>'
            '<button type="button" class="btn btn-primary" data-fallback-save onclick="mcSaveApiFallback(this)">Save</button></div>'
            '</div></div>'+js('api_fallback'))
