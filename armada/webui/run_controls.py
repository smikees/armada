"""Shared owner controls for provider, realm, agent and approved jobs."""
from ..assets import js
from ._base import E


def choice(name, value, label, options):
    return (f'<label class="mc-label" for="{E(name)}">{E(label)}</label><select class="mc-field" id="{E(name)}" data-run-control="{E(name)}">'
            + ''.join(f'<option value="{E(k)}" {"selected" if str(value or "")==k else ""}>{E(v)}</option>' for k,v in options)+'</select>')


def fields(job, *, prefix='j-', inherited=True):
    controls = [choice(prefix+'plan_limit_action', job.get('plan_limit_action'), 'At the subscription limit',
                       ([('', 'Inherit')] if inherited else [])+[('api','Use API key'),('wait','Wait for reset'),('fail','Fail')]),
                choice(prefix+'connector_limit_action', job.get('connector_limit_action'), 'If a connector needs the subscription',
                       ([('', 'Inherit')] if inherited else [])+[('wait','Wait for reset'),('fail','Fail')])]
    for key,label in [('api_run_ceiling_usd','API ceiling per run — USD'), ('api_model','API model (empty uses the same model)')]:
        number = key.endswith('_usd')
        controls.append(f'<label class="mc-label" for="{prefix}{key}">{label}</label><input class="mc-field" id="{prefix}{key}" '
                        f'data-run-control="{key}" value="{E(str(job.get(key) or ""))}" '+('type="number" min="0.0001" step="0.01"' if number else '')+'>')
    return ''.join(controls)


def panel(root=None, agent='', *, global_provider=False):
    from .api_fallback import setup
    if global_provider:
        return setup('claude')
    from .. import run_policy
    values = run_policy._read().get('scopes', {}).get(run_policy.scope_id(root, agent), {})
    prefix = 'rp-agent-' if agent else 'rp-realm-'
    title = 'Run limits & fallback'
    content = (setup('claude', root, agent) if agent else '')+fields(values, prefix=prefix)
    numbers = []
    if not agent:
        content += ('<label class="mc-label"><input type="checkbox" data-run-control="coordinator_may_propose_changes" '
                    + ('checked' if values.get('coordinator_may_propose_changes') else '')
                    + '> Allow coordinators to propose changes to other agents’ existing jobs</label>')
        numbers += [('default_job_timeout','Default agent-job ceiling — seconds (empty means No limit)',''),
                    ('agent_inactivity_minutes','Stop after no engine event — minutes',30),
                    ('agent_soft_mark_minutes','Notify after running — minutes (0 disables)',60),
                    ('critical_usage_percent','Defer unattended work above session use — %',80)]
        numbers += [('coordinator_daily_cap', 'Coordinator starts per day across this realm', 6)]
    for key,label,default in numbers:
        content += f'<label class="mc-label" for="{prefix}{key}">{label}</label><input class="mc-field" type="number" step="any" id="{prefix}{key}" data-run-control="{key}" value="{E(str(values.get(key, default)))}">'
    return (f'<details class="mc-run-controls" data-agent="{E(agent)}" data-global="{str(global_provider).lower()}"><summary>{title}</summary>'
            f'<p class="mc-hint">Owner-only choices, saved on this machine. API fallback requires an enabled key and compatible connectors. The provider enforces its spending limit.</p>{content}'
            '<p><button type="button" class="btn btn-secondary" onclick="mcSaveRunControls(this)">Save run controls</button> '
            '<span role="status" data-run-feedback></span></p></details>'+js('run_controls'))


def worker_controls():
    """Optional isolation stays out of normal API setup."""
    from .. import worker, realm_registry
    isolation = worker.status()
    folders = isolation['folders'] if isolation['enabled'] else [row['path'] for row in realm_registry.load()]
    return ('<details class="mc-worker-controls"><summary>Isolated execution (advanced)</summary>'
            '<p class="mc-hint">Optional: run agents under a separate non-admin Windows account. This needs administrator consent, '
            'folder access and separate provider sign-ins. API fallback does not require it.</p>'
            f'<p data-worker-state role="status">{E("Ready: "+isolation["username"] if isolation["ready"] else isolation["error"] or "Not set up")}</p>'
            '<label class="mc-label" for="worker-folders">Folders shared with agents — one absolute path per line</label>'
            f'<textarea class="mc-field" id="worker-folders" data-worker-folders rows="3">{E(chr(10).join(folders))}</textarea>'
            '<p><button type="button" class="btn btn-secondary" onclick="mcSetupWorker(this)">Set up / repair worker</button> '
            '<button type="button" class="btn btn-secondary" onclick="mcVerifyWorker(this)">Verify isolation</button></p></details>'+js('run_controls'))


def job_fields(job):
    command = job.get('kind') == 'command'
    placeholder = '300' if command else 'No limit'
    hint = ('Command jobs keep their 300-second default when this field is empty.' if command else
            'No limit when empty, unless this realm has a default job ceiling. Inactivity monitoring still applies.')
    return ('<details class="mc-run-controls"><summary>Time limit, fallback &amp; priority</summary>'
            '<label class="mc-label" for="j-timeout">Time limit — seconds</label>'
            f'<input class="mc-field" id="j-timeout" type="number" min="0.001" step="any" value="{E(str(job.get("timeout") or ""))}" placeholder="{placeholder}">'
            f'<p class="mc-hint">{hint}</p>'
            f'<label><input id="j-critical" type="checkbox" {"checked" if job.get("critical") else ""}> Critical job — queue priority and API fallback when enabled</label>'
            + fields(job)+'</details>')
