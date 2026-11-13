"""Owner-facing readiness controls; rendering reads local state only."""
import datetime as dt
from pathlib import Path
from ._base import E
from ..assets import js


def summary(job):
    from ..job_rules import FIELDS
    import json
    choices = {key: job[key] for key in FIELDS if job.get(key)}
    return ('<details open><summary>Start conditions &amp; recovery to approve</summary><pre style="white-space:pre-wrap">'
            +E(json.dumps(choices, indent=2, ensure_ascii=False))+'</pre></details>') if choices else ''


def fields(job, root, agent):
    from .. import capabilities, command_secrets, scheduler
    choices = [(aid+'/'+jid, j.get('name') or jid) for aid, jid, j in scheduler.iter_jobs(Path(root))
               if (aid, jid) != (agent, job.get('id')) and not j.get('_record_error')]
    def options(value='', empty='Choose a job'):
        return '<option value="">'+empty+'</option>'+''.join(
            f'<option value="{E(key)}" {"selected" if key==value else ""}>{E(name)} ({E(key)})</option>' for key, name in choices)
    def dependency(row):
        outcomes = row.get('outcome', ['ok', 'warn'])
        return ('<div data-dependency style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0">'
                f'<select class="mc-field" data-job aria-label="Dependency job">{options(row.get("agent", "")+"/"+row.get("job", ""))}</select>'
                f'<label>Result no older than <input type="number" min="1" max="10080" data-age value="{row.get("max_age_minutes",60)}" aria-label="Result age in minutes"> min</label>'
                f'<label><input type="checkbox" data-ok {"checked" if "ok" in outcomes else ""}> Success</label>'
                f'<label><input type="checkbox" data-warn {"checked" if "warn" in outcomes else ""}> Warning</label>'
                '<button type="button" class="btn btn-secondary" onclick="this.closest(\'[data-dependency]\').remove()">Remove</button></div>')
    allowed = set(capabilities.execution_policy(root, agent).allowed_mcp_ids)
    checks = ''.join(f'<label style="display:block"><input type="checkbox" data-required-connector value="{E(c["id"])}" '
                     f'{"checked" if c["id"] in job.get("requires_connectors",[]) else ""}> {E(c.get("name") or c["id"])}</label>'
                     for c in capabilities.catalogue(root)['connectors'] if c['id'] in allowed)
    window, fallback = job.get('start_window') or {}, job.get('fallback_job') or {}
    secrets = sorted(set(command_secrets.names(root)) | set(job.get('secrets', [])))
    secret_checks = ''.join(f'<label style="display:block"><input type="checkbox" data-command-secret value="{E(name)}" '
                           f'{"checked" if name in job.get("secrets",[]) else ""}> {E(name)}</label>' for name in secrets)
    return ('<details class="mc-run-controls"><summary>Start conditions &amp; recovery</summary>'
            '<p class="mc-hint">These choices are covered by your approval. Waiting spends no model tokens and holds no execution slot.</p>'
            '<p class="mc-label">Required connectors</p>'+ (checks or '<p class="mc-hint">Grant this agent a connector in Capabilities first.</p>')+
            '<label class="mc-label" for="j-start-deadline">Wait for connectors — minutes after scheduled start</label>'
            f'<input class="mc-field" id="j-start-deadline" type="number" min="1" max="1440" value="{job.get("start_deadline_minutes",90)}">'
            '<p class="mc-label">Start window (optional)</p><label>From '
            f'<input type="time" id="j-window-from" value="{E(window.get("from", ""))}"></label> <label>Until '
            f'<input type="time" id="j-window-until" value="{E(window.get("until", ""))}"></label>'
            '<p class="mc-hint">Uses the realm timezone and scheduled days. An end before the start means the next day.</p>'
            '<p class="mc-label">Wait for successful jobs</p><div id="j-dependencies">'+''.join(dependency(row) for row in job.get('after', []))+'</div>'
            '<template id="j-dependency-template">'+dependency({})+'</template>'
            '<button type="button" class="btn btn-secondary" onclick="document.getElementById(\'j-dependencies\').append(document.getElementById(\'j-dependency-template\').content.cloneNode(true))">Add dependency</button>'
            '<label class="mc-label" for="j-window-end">If dependencies are unfinished when the window closes</label>'
            f'<select class="mc-field" id="j-window-end"><option value="fail">Fail without starting</option><option value="run_anyway" {"selected" if job.get("on_window_end")=="run_anyway" else ""}>Run with a warning</option></select>'
            '<p class="mc-hint">A required connector must still be healthy. Without a window, the wait uses the start deadline above.</p>'
            '<label class="mc-label" for="j-retry-delays">Retry delays — seconds, separated by commas (empty uses 30, 60, 120)</label>'
            f'<input class="mc-field" id="j-retry-delays" value="{E(", ".join(map(str, job.get("retry_backoff_seconds",[]))))}">'
            '<label class="mc-label" for="j-fallback-job">Approved job to run after a safely replayable failure</label>'
            f'<select class="mc-field" id="j-fallback-job">{options(fallback.get("agent", "")+"/"+fallback.get("job", ""), "No fallback")}</select>'
            '<p class="mc-hint">The fallback must be enabled and approved. Safeguards against repeating side effects still apply.</p>'
            f'<label><input type="checkbox" id="j-coordinator-start" {"checked" if job.get("coordinator_may_start") else ""}> The coordinator may start this approved job</label>'
            '<label class="mc-label" for="j-coordinator-cap">Coordinator starts per day for this job</label>'
            f'<input class="mc-field" type="number" min="1" max="100" id="j-coordinator-cap" value="{job.get("coordinator_daily_cap",2)}">'
            '<p class="mc-hint">The realm daily cap also applies. A coordinator cannot change the prompt or run an overlapping copy.</p>'
            '<p class="mc-label">Command credentials</p>'+(secret_checks or '<p class="mc-hint">Add named command credentials in App Settings → Advanced.</p>')+
            '<p class="mc-hint">Command jobs only. Receives ARMADA_SECRET_NAME in that process environment.</p></details>'+js('job_readiness'))


def wait_label(root, agent, jid):
    from .. import job_waits, scheduler, util
    row = job_waits.pending(root, agent, jid)
    if not row:
        return ''
    tz = scheduler.now_in(util.read_json_state(Path(root)/'realm.json')).tzinfo
    start = dt.datetime.fromtimestamp(row['since'], tz).strftime('%H:%M')
    end = dt.datetime.fromtimestamp(row['deadline'], tz).strftime('%H:%M')
    return f'Waiting since {start}, until {end}: ' + (row.get('reason') or 'execution capacity')
