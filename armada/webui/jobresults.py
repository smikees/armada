"""Shared execution/audit/delivery evidence for realm and agent job outputs."""
from ._base import E
from .. import job_results


def capture_html(event):
    capture = event.get("capture")
    if not capture:
        return ""
    count = int(capture.get("count", 0))
    label = "Capture incomplete" if capture.get("status") == "incomplete" else "Captured results"
    manifest = capture.get("manifest", "")
    link = (f' · <a href="#" data-local-file="{E(manifest)}">manifest.jsonl</a>' if manifest else "")
    return (f'<div class="mc-job-capture"><strong>{label}:</strong> {count} result(s){link}'
            + ''.join(f'<div>{E(reason)}</div>' for reason in capture.get("errors", [])) + '</div>')


def result_html(event: dict, content: dict) -> str:
    captured = capture_html(event)
    result = event.get("result")
    if not isinstance(result, dict):
        markers = job_results.LEGACY.findall(content.get("raw_final_answer") or content.get("content") or "")
        legacy = markers[-1] if markers else str(event.get("status") or "unknown")
        return captured + (f'<div class="mc-job-result"><strong>Legacy result: {E(legacy)}</strong>'
                '<div>Less detailed — execution, audit and delivery were not recorded independently. '
                'SUCCESS does not establish a clear audit.</div>'
                + (f'<div>Historical error: {E(str(event.get("summary") or ""))}</div>' if legacy == "FAILED" else "") + '</div>')
    evidence = result["evidence"]
    rows = [f'<div><strong>Execution:</strong> {E(result["execution"].replace("_", " "))}</div>',
            f'<div><strong>Audit:</strong> {E(result["audit_outcome"].replace("_", " "))}</div>']
    for delivery in result["delivery"]:
        rows.append(f'<div><strong>{E(delivery["destination"])}:</strong> {E(delivery["status"])}'
                    + (f' — {E(delivery["error"])}' if delivery.get("error") else '') + '</div>')
    if not result["delivery"]:
        rows.append('<div><strong>Delivery:</strong> no required destination recorded</div>')
    for key, label in (("findings", "Findings"), ("missing_inputs", "Missing inputs"),
                       ("risk_gates", "Unresolved risk gates"), ("operational_errors", "Agent-recorded operational errors")):
        if evidence.get(key):
            rows.append(f'<div><strong>{label}</strong><ul>' + ''.join(f'<li>{E(x)}</li>' for x in evidence[key]) + '</ul></div>')
    errors = list(dict.fromkeys(result.get("app_errors", []) + content.get("app_errors", [])))
    if errors:
        rows.append('<div><strong>Armada errors / verification</strong><ul>'
                    + ''.join(f'<li>{E(x)}</li>' for x in errors) + '</ul></div>')
    if evidence.get("outputs"):
        rows.append('<details><summary>Output evidence</summary><ul>' + ''.join(
            f'<li>{E(x["path"])} — {"validated" if x.get("validated") else "not validated"}</li>'
            for x in evidence["outputs"]) + '</ul></details>')
    receipts = [d for d in result["delivery"] if d.get("receipt")]
    if receipts:
        import json
        rows.append('<details><summary>Delivery receipts</summary>' + ''.join(
            f'<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{E(json.dumps(d["receipt"], ensure_ascii=False, indent=2))}</pre>'
            for d in receipts) + '</details>')
    if result.get("detail_level") != "structured":
        rows.append(f'<div>Less detailed legacy result: {E(result.get("legacy_result") or "not recorded")}. '
                    'No clean audit is inferred.</div>')
    annotation = event.get("annotation")
    if annotation:
        rows.append(f'<div><strong>Historical correction:</strong> {E(annotation["reason"])}</div>'
                    f'<div>Original status: {E(event.get("original_status") or "")} · '
                    f'Original error: {E(event.get("original_summary") or "")}</div>')
    if result["audit_outcome"] in ("incomplete", "findings") or evidence.get("risk_gates"):
        rows.append('<div><strong>Completion does not mean the portfolio passed its checks. Unresolved risk gates remain in force.</strong></div>')
    return captured + '<div class="mc-job-result">' + ''.join(rows) + '</div>'
