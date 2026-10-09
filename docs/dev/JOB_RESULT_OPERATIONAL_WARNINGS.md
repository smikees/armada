# Operational warnings and required prerequisites

Prepared for 0.99.97; see [release verification](RELEASE_0_99_97.md) for publication status.

The versioned result keeps execution, audit and delivery independent. A produced report can
complete while its audit is incomplete, and a failure notice can be delivered while the business
job fails. Required operational prerequisites must be classified according to the requested
work: an unavailable fresh source that prevents the work means execution failed, even if an
error report was written.

`job_results.status()` previously ignored `evidence.operational_errors` when all other aspects
passed. A successful file write and validated delivery could therefore suppress a recorded
fetch failure. Nonempty operational errors now retain an overall warning, without changing a
completed execution to failed. `label()` adds “operational warnings” for completed runs, and
`reason()` exposes the first recorded operational error when no application error takes priority.

The contract prompt now distinguishes required operational prerequisites from incomplete
evidence in a completed reviewer report. Existing host-validated fresh output and per-run receipt
checks remain unchanged. Runtime failures still override model completion claims. Historical
reports are not rewritten.

Regression tests verify a successful report/delivery with an operational fetch error remains a
warning, and a missing required input remains failed despite a validated failure-notice receipt.
Private realm job/script changes and their offline integration tests are kept outside the public
source tree.
