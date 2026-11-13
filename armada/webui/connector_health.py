"""Local heartbeat and command-credential settings, with secrets entered in a modal."""
import datetime as dt
from ._base import E
from ..assets import js


def card(root, cid):
    from .. import connector_health
    rows = [r for r in connector_health.snapshot(root)['connectors'].values() if r['id'] == cid]
    def stamp(value):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).astimezone().strftime('%d %b %H:%M') if value else 'never'
    text = '\n'.join(f'{r["provider"].title()}: {r["state"]} · checked {stamp(r["checked_at"])} · last up {stamp(r.get("last_up_at"))} · '
                    f'{r.get("uptime_percent",0):.1f}% of checks passed in 30 days. '+r.get('reason','') for r in rows)
    return '<p class="mc-hint" style="margin:10px 20px;white-space:pre-line" data-connector-health="'+E(cid)+'">'+E(text or 'No heartbeat recorded.')+'</p>'


def watch_controls(root):
    from .. import capabilities, connector_health
    choices = connector_health.settings(root)
    checks = ''.join(f'<label style="display:block;margin:8px 0"><input type="checkbox" data-watch value="{E(c["id"])}" '
                     f'{"checked" if c["id"] in choices.get("watched",[]) else ""}> {E(c.get("name") or c["id"])}</label>'
                     for c in capabilities.catalogue(root)['connectors'])
    fields = ''.join(f'<label class="mc-label">{label}<input class="mc-field" type="number" min="1" max="1440" data-health-setting="{key}" value="{choices.get(key,default)}"></label>'
                     for key,label,default in [('interval_minutes','Weekday interval — minutes',15), ('near_job_minutes','Interval near a job — minutes',5), ('lead_minutes','Begin faster checks before a job — minutes',30)])
    return ('<button type="button" class="btn btn-secondary" onclick="document.getElementById(\'connector-watch-dialog\').showModal()">Connector monitoring</button>'
            '<dialog id="connector-watch-dialog" class="mc-frame" style="width:min(560px,90vw);max-height:85vh;overflow:auto">'
            '<h2>Connector monitoring</h2><p>Checks run without a model or tokens. Required connectors are also checked before their jobs start.</p>'+checks+fields+
            '<p data-feedback role="status"></p><button class="btn btn-primary" type="button" onclick="mcSaveWatches(this)">Save</button> '
            '<button class="btn btn-secondary" type="button" onclick="this.closest(\'dialog\').close()">Close</button></dialog>'+js('connector_health'))


def secrets_controls(root):
    from .. import command_secrets
    if not root:
        return ''
    names = ', '.join(command_secrets.names(root)) or 'None'
    return ('<p><button type="button" class="btn btn-secondary" onclick="document.getElementById(\'command-secret-dialog\').showModal()">Command credentials</button></p>'
            '<dialog id="command-secret-dialog" class="mc-frame" style="width:min(560px,90vw)">'
            '<h2>Command credentials</h2><p>Encrypted on this Windows account, outside realm folders. Only approved command jobs receive selected credentials. Programs running under your Windows account can technically access them.</p>'
            f'<p>Configured in this realm: <span data-secret-names>{E(names)}</span></p>'
            '<label class="mc-label" for="command-secret-name">Name (for example ibkr_read)</label><input class="mc-field" id="command-secret-name" pattern="[a-z][a-z0-9_]{0,63}" autocomplete="off">'
            '<label class="mc-label" for="command-secret-value">Secret value</label><input class="mc-field" id="command-secret-value" type="password" autocomplete="new-password">'
            '<p class="mc-hint">This becomes ARMADA_SECRET_IBKR_READ in a command job that names ibkr_read. Values are never shown again.</p>'
            '<p data-feedback role="status"></p><button type="button" class="btn btn-primary" onclick="mcSaveCommandSecret(this,false)">Save</button> '
            '<button type="button" class="btn btn-secondary" onclick="mcSaveCommandSecret(this,true)">Remove named credential</button> '
            '<button type="button" class="btn btn-secondary" onclick="this.closest(\'dialog\').querySelector(\'input[type=password]\').value=\'\';this.closest(\'dialog\').close()">Close</button></dialog>'+js('connector_health'))
