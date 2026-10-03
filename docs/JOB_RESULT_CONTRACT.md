# Job result contract v1

Armada supplies the current run ID and the result schema in each scheduled agent job prompt.
Command jobs receive `ARMADA_RUN_ID` in their environment. Return a human-readable answer,
then exactly one final `<armada_job_result>` JSON block. Accounting persists the validated
result under the same individual `run_id`; the transcript retains `raw_final_answer`.

```json
{
  "schema_version": 1,
  "run_id": "the-current-run-id",
  "execution": "completed",
  "audit_outcome": "incomplete",
  "delivery": [
    {"destination": "telegram", "status": "sent", "receipt_path": "ABSOLUTE_RECEIPT_PATH"}
  ],
  "evidence": {
    "outputs": [{"path": "ABSOLUTE_REPORT_PATH", "required": true}],
    "findings": ["Describe the breach and its evidence"],
    "missing_inputs": ["Historical risk data unavailable"],
    "operational_errors": [],
    "risk_gates": ["Unresolved mandatory check; do not clear the gate"]
  }
}
```

Execution is `completed`, `failed`, `stopped`, or `timed_out`. Audit is `clear`, `findings`,
`incomplete`, or `not_applicable`. Incomplete audits may also contain findings. Each delivery
destination has `sent`, `failed`, `unknown`, or `not_required`. Required reports must exist,
be non-empty and belong to the current run; approved completion checks also remain in force.
Job JSON may add `result_contract.required_outputs` (absolute paths) and
`result_contract.required_destinations` (destination names). Machine-approved completion
checks supplement these requirements and cannot be disabled by the agent's result block.

A receipt is JSON with `schema_version: 1`, matching `run_id` and `destination`, `status: sent`,
`sent_at` with timezone within the current execution, and actual provider `message_ids`
(positive integers) or a provider `receipt_id`. Optional `job_id` must match. Keep receipts
within the approved folders. Armada snapshots verified receipt contents into the result;
later overwrites cannot alter delivery history. Never manufacture a receipt by copying an
older delivery. Finance's maintained sender (`tools/finance_telegram_sender.py`) accepts
`--job-id` and `--run-id` and writes a separate immutable receipt with provider message IDs,
document path and SHA-256. Its duplicate prevention does not attribute an earlier delivery
to a later run. Deploy the helper into the approved folder used by the relevant job.

Contract validation defects produce visible verification warnings rather than an inferred
clean audit. Missing required reports fail execution; delivery errors do not. Runtime
exceptions, stops and timeouts override agent execution claims while preserving partial
outputs. `app_errors` and `validation_errors` are separate from agent evidence and findings.
Contradictory clean audit claims retain their findings and become incomplete with a warning.

Legacy `ARMADA_JOB_RESULT: SUCCESS/FAILED` markers remain supported. Store `legacy_result`,
`legacy_explanation`, and `detail_level: legacy`; never infer clear audit from SUCCESS.
Unstructured non-audit jobs are identified as such. Corrections use a versioned sidecar in
`runs/annotations/<run_id>.json`, recording rationale and correlated evidence without editing
original accounting or transcripts. Historical receipts without run IDs require an explicit
correction supported by the original run's tool activity, timing and artifacts; they are
never accepted by the automatic new-run receipt validator.
