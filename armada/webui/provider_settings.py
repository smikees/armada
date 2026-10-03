"""Shared connection controls for setup and App Settings; no probes during rendering."""
from ..assets import js
from ..icons import _icon, _provider_logo
from ._base import E


def connections(*, setup=False):
    from .. import providers
    connected = providers.connected()
    cards = []
    for provider, title, icon, url in (
        ("claude", "Claude", "claude", "https://code.claude.com/docs/en/setup"),
        ("codex", "Codex", "codex", "https://developers.openai.com/codex/cli/"),
        ("gemini", "Gemini", "gemini", "https://antigravity.google/docs/cli/install/"),
    ):
        plan_id = f'provider-{provider}-plan'
        plan_prefix = "ChatGPT" if provider == "codex" else "Gemini" if provider == "gemini" else "Claude"
        plan = (f'<span class="mc-pill" id="{plan_id}" data-plan-prefix="{plan_prefix}"></span>' if setup else
                f'<div class="mc-provider-plan mc-hint" id="{plan_id}" data-plan-prefix="{plan_prefix}" hidden></div>')
        feedback = f'<span id="provider-{provider}-feedback" class="mc-hint" role="status"></span>'
        installed = f'<span class="mc-pill" id="provider-{provider}-installed">Checking installation…</span>'
        if setup:
            header = (f'<strong class="mc-provider-head">{_provider_logo(provider,20,True)}{title}</strong>'
                      f'<div class="mc-su-provider-states"><div><span>CLI status:</span>{installed}</div>'
                      f'<div><span>Authentication status:</span><span class="mc-pill" data-auth-pill="true" '
                      f'id="provider-{provider}-status" role="status">Checking…</span></div>'
                      f'<div class="mc-su-provider-subscription" id="provider-{provider}-subscription" hidden>'
                      f'<span>Subscription type:</span>{plan}</div></div>')
        else:
            header = (f'<strong class="mc-provider-head">{_provider_logo(provider,20,provider in connected)}{title}{installed}</strong>'
                      f'<div class="mc-provider-plan-slot">{plan}</div>'
                      f'<p id="provider-{provider}-status" role="status" class="mc-provider-statusline">Checking connection…</p>')
        cards.append(f'<div class="mc-frame mc-provider-card{" mc-su-provider-card" if setup else ""}" data-connection="{provider}">'
            + header + ('<div class="mc-su-provider-details">' + feedback if setup else '<div class="mc-provider-login-slot">') +
            f'<div class="mc-provider-login-url" id="provider-{provider}-url-wrap" hidden><a id="provider-{provider}-url" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"></a></div>'
            '</div>' + (feedback if not setup else '') +
            '<div class="mc-provider-actions">'
            f'<button class="btn btn-secondary" id="provider-{provider}-connect" hidden onclick="mcConnection(\'{provider}\',\'connect\',this)" title="Opens the provider’s website in your browser">'
            f'<span data-signin-label data-default-label="Sign in">Sign in</span>{_icon("external-link",13)}</button>'
            f'<button class="btn btn-secondary mc-provider-recheck" id="provider-{provider}-recheck" onclick="mcRecheckProvider(\'{provider}\',this)">{_icon("refresh-cw",13)}<span>Recheck</span></button>'
            f'<button class="btn btn-secondary" id="provider-{provider}-disconnect" hidden onclick="mcConnection(\'{provider}\',\'disconnect\',this)">Disconnect</button>'
            f'<button class="btn btn-secondary" id="provider-{provider}-install" hidden onclick="mcConnection(\'{provider}\',\'install\',this)">Install {"Antigravity CLI" if provider == "gemini" else title + " CLI"}</button>'
            f'<button class="btn btn-secondary" id="provider-{provider}-open" hidden onclick="mcConnection(\'{provider}\',\'open-login\',this)">Open sign-in page</button>'
            f'<button class="btn btn-secondary" id="provider-{provider}-cancel" hidden onclick="mcConnection(\'{provider}\',\'cancel-login\',this)">Cancel sign-in</button>'
            f'<a id="provider-{provider}-guide" href="{E(url)}" target="_blank" rel="noopener" hidden>Installation guide</a>'
            f'</div></div>')
    guidance = ('<p class="mc-hint">For Codex or Claude, a paid '
                '<a href="https://learn.chatgpt.com/docs/pricing" target="_blank" rel="noopener noreferrer">ChatGPT Plus or Pro</a> '
                'or a <a href="https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan" '
                'target="_blank" rel="noopener noreferrer">Claude Pro or Max</a> subscription is needed. However, '
                '<a href="https://antigravity.google/pricing" target="_blank" rel="noopener noreferrer">Gemini through Antigravity CLI</a> '
                'can be used with a free-tier account.</p>') if setup else ''
    return (('<p>Connect at least one engine via its CLI (Anthropic - Claude CLI, OpenAI - Codex CLI, Google - Antigravity CLI): install it and sign in.</p>' if setup else '')
            + '<div class="mc-provider-grid' + (' mc-su-provider-grid' if setup else '') + '">' + ''.join(cards) + '</div>'
            + '<p style="font-size:12px;color:var(--text-muted)">Disconnecting stops Armada from using models from that provider.</p>'
            + guidance + js("providers"))


def alexander_settings(root):
    from ..alexander import config
    from .. import models
    from .. import verbosity
    settings = config.load()
    choices = [("auto", "Automatic (default)")] + models.options(root)
    if settings["model"] not in dict(choices):
        choices.append((settings["model"], settings["model"] + " — unavailable"))
    opts = ''.join(f'<option value="{E(k)}" {"selected" if k == settings["model"] else ""}>{E(v)}</option>' for k, v in choices)
    eff = ''.join(f'<option value="{e}" {"selected" if e == settings["effort"] else ""}>{"Automatic" if e == "auto" else e.title()}</option>' for e in config.efforts(settings["model"]))
    verb = ''.join(f'<option value="{v}" {"selected" if v == settings["verbosity"] else ""}>{E(label)} — {E(desc)}</option>'
                   for v, (label, desc, _) in verbosity.LEVELS.items())
    return ('<div style="margin-top:20px"><h3>Alexander</h3>'
            '<p>Alexander is your guide to Armada, helping you understand the app and resolve problems.</p>'
            '<div class="mc-realm-model-defaults">'
            f'<div><label class="mc-label" for="alexander-model">Model</label><select id="alexander-model" data-provider-models class="mc-field">{opts}</select></div>'
            f'<div><label class="mc-label" for="alexander-effort">Thinking</label><select id="alexander-effort" class="mc-field">{eff}</select></div>'
            f'<div><label class="mc-label" for="alexander-verbosity">Verbosity</label><select id="alexander-verbosity" class="mc-field">{verb}</select></div></div>'
            '<p id="alexander-settings-status" role="status"></p></div>')
