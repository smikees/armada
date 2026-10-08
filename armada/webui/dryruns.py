"""Inline draft-only job controls and review output, using existing Jobs styles."""
from pathlib import Path

from ._base import E, _md


def controls(agent, job_id, job, *, open=False):
    command = job.get("kind") == "command" or bool(job.get("run") or job.get("command"))
    field = "padding:6px 8px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;max-width:100%"
    return (f'<details class="mc-job-section mc-dry-runs" data-dry-agent="{E(agent)}" '
        f'data-dry-job="{E(job_id)}" data-dry-command="{"1" if command else "0"}"'
        f'{" open" if open else ""}><summary>Dry runs</summary><div class="mc-job-section-body">'
        f'<p style="font-size:12px;color:var(--text-dim);margin:0 0 12px">Create temporary drafts to test '
        f'{"the saved dry-run command" if command else "a model using saved file inputs"}. '
        'Production outputs, model and schedule stay unchanged.</p>'
        '<div style="display:flex;align-items:end;gap:8px;flex-wrap:wrap">'
        + (f'<label style="display:grid;gap:4px;font-size:12px">Test model<select class="mc-dry-model" '
           f'aria-label="Dry-run model" style="{field}"><option value="">Choose a model…</option></select></label>'
           if not command else '<span style="font-size:12px">Uses the draft-only command from Job settings.</span>')
        + '<button class="btn btn-secondary btn-sm mc-dry-start" onclick="mcDryStart(this)">Start dry run</button>'
        '<button class="btn btn-secondary btn-sm mc-dry-stop" onclick="mcDryStop(this)" hidden style="display:none">Stop</button>'
        '<span class="mc-dry-message" role="status" style="font-size:12px"></span></div>'
        f'<p style="font-size:11.5px;color:var(--text-muted)">Kept for {E(str(job.get("dry_run_keep_days", 7)))} days '
        'after completion. Model tests cannot publish, send, use a shell, or refresh live connectors.</p>'
        f'<label style="display:grid;gap:4px;font-size:12px">Dry-run history<select class="mc-dry-history" '
        f'aria-label="Dry-run output" onchange="mcDrySelect(this)" style="{field}"><option value="">Latest dry run</option></select></label>'
        '<div class="mc-dry-output" style="margin-top:12px;overflow-wrap:anywhere">Open to load dry runs.</div>'
        '</div></details>')


def result_html(root, info):
    from .. import dry_runs, inspection, util
    folder = dry_runs.directory(root, info["agent"], info["job"], info["run_id"])
    status = E(info["status"].replace("_", " ").title())
    model = E(info.get("actual_model") or info.get("model") or "Command")
    html = f'<div><strong>{status}</strong> · {model} · requested by {E(info["requested_by"])}</div>'
    html += f'<p style="font-size:12px;color:var(--text-dim)">{E(info["limitations"])}</p>'
    if info.get("error"):
        html += f'<p role="alert" style="color:var(--status-bad)">{E(info["error"])}</p>'
    if (folder / "transcript.json").exists():
        content = util.read_json_state(inspection.checked_path(folder / "transcript.json", [Path(root).resolve()], must_exist=True))
        if info.get("result"):
            from .jobresults import result_html as evidence_html
            html += evidence_html(info, content)
        html += '<div class="mc-md">' + _md(content.get("content") or "No final answer was produced.") + '</div>'
    files = dry_runs.output_files(folder)
    if files:
        html += '<details><summary>Draft files</summary><ul>' + ''.join(
            f'<li><a href="#" data-local-file="{E(f["path"])}">{E(f["name"])}</a> · {f["bytes"]} bytes</li>' for f in files) + '</ul></details>'
    html += f'<div style="font-size:11.5px;color:var(--text-muted)">Folder: {E(str(folder / "output"))}</div>'
    return html
